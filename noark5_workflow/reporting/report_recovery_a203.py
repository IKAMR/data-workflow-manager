"""Read-only, reconnectable report export for unstable local/removable disks.

Build the *same* report via report_service_a20 on stable local storage before
publishing any files to the chosen destination.  A temporary I/O interruption
restarts only the report render (never XPath, Arkade, imports or job operations).
Once built, publication resumes file by file from the complete local copy.

The caller runs this worker OFF the Tk main thread.  Callbacks execute on the
worker thread and must be relayed to Tk through a queue / after().
"""
from __future__ import annotations

import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import traceback
from datetime import datetime, timezone
from uuid import uuid4
from typing import Callable


# Windows device I/O errors: not ready, bad sector, missing share, disconnected
# device, delayed I/O, and unavailable network.  EINVAL (22) is *not* on this
# list: it may also represent an invalid file name or programming error.
TRANSIENT_WINERRORS = frozenset({21, 23, 53, 55, 64, 67, 1117, 1167, 121, 1231})
TRANSIENT_ERRNOS = frozenset(x for x in (
    errno.EIO, errno.ENODEV, errno.ENXIO, errno.ETIMEDOUT,
    getattr(errno, 'ESTALE', None), getattr(errno, 'ENETDOWN', None),
) if x is not None)
EXPORT_FORMATS = frozenset(('.html', '.json', '.pdf', '.csv'))


class ExportStopped(Exception):
    """Export was cancelled; no report actions or data were changed."""


class StorageUnavailable(OSError):
    """Previously present input/output storage is temporarily inaccessible."""


class StorageChanged(RuntimeError):
    """A Windows drive letter now refers to a different storage volume."""


def _report_state_root() -> Path:
    """Put recovery logs/cache on the master client, NEVER on an unstable disk."""
    if os.name == 'nt':
        home = os.environ.get('LOCALAPPDATA')
        if home:
            return Path(home) / 'IKAMR' / 'DWM' / 'report_operations'
    return Path.home() / '.local' / 'state' / 'ikamr-dwm' / 'report_operations'


def _volume_serial(anchor: Path) -> int | None:
    """Best-effort Windows drive identity; never infer identity by letter alone."""
    if os.name != 'nt':
        return None
    try:
        import ctypes
        serial = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            str(anchor), None, 0, ctypes.byref(serial), None, None, None, 0)
        return int(serial.value) if ok else None
    except (AttributeError, OSError, ValueError):
        return None


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _same_file(source: Path, destination: Path) -> bool:
    try:
        return (destination.is_file() and destination.stat().st_size == source.stat().st_size
                and _digest(source) == _digest(destination))
    except (OSError, ValueError):
        return False


def _work_paths(jobs) -> tuple[Path, ...]:
    # Report data live under the DWM operation roots; source_extraction can be
    # a huge Noark source tree and is NEVER scanned or copied here.
    seen: set[str] = set()
    paths = []
    for job in jobs:
        # Prefer the resolved path.  An obsolete legacy work_operations drive
        # must not force an otherwise available extraction to wait forever.
        value = (getattr(job, '_effective_work_operations', None)
                 or getattr(job, 'work_operations', None))
        if not value:
            continue
        path = Path(value)
        canonical = os.path.normcase(os.path.abspath(str(path)))
        if canonical not in seen:
            seen.add(canonical)
            paths.append(path)
    return tuple(paths)


def _retryable(exc: BaseException) -> bool:
    return (isinstance(exc, StorageUnavailable)
            or isinstance(exc, OSError)
            and (getattr(exc, 'winerror', None) in TRANSIENT_WINERRORS
                 or getattr(exc, 'errno', None) in TRANSIENT_ERRNOS))


class ReportRecoverySession:
    """One report export session; never mutates input results or job state."""

    def __init__(self, directory, jobs, options, *, prefix='', formats=('html',),
                 on_progress: Callable | None = None, on_warning: Callable | None = None,
                 confirm_overwrite: Callable | None = None,
                 cancelled: threading.Event | None = None,
                 writer: Callable | None = None,
                 state_root: Path | None = None, poll_seconds: float = 4.0,
                 probe: Callable | None = None):
        from .report_service_a20 import _prefix, _validate_jobs, SUPPORTED_FORMATS
        self.jobs = tuple(jobs)
        _validate_jobs(self.jobs)
        self.options = options
        self.directory = Path(directory)
        self.prefix = _prefix(prefix)
        self.formats = tuple(dict.fromkeys(str(f).lower() for f in formats))
        if not self.formats or any(f not in SUPPORTED_FORMATS for f in self.formats):
            raise ValueError('Ugyldig rapportformat')
        self.cancelled = cancelled if cancelled is not None else threading.Event()
        self.on_progress = on_progress
        self.on_warning = on_warning
        self.confirm_overwrite = confirm_overwrite
        self.writer = writer
        self.poll_seconds = max(0.01, float(poll_seconds))
        self.probe_override = probe
        self.work_paths = _work_paths(self.jobs)
        self.seen_work_paths: set[Path] = set()
        self.identities: dict[str, int] = {}
        self.overwrite_allowed = False
        self.session_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:10]
        self.state_root = Path(state_root) if state_root else _report_state_root()
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.log_path = self.state_root / (self.session_id + '.jsonl')
        # Retain a *complete local report* until all requested copies are done.
        # This can also be inspected if output publication fails persistently.
        self.session_dir = self.state_root / ('cache-' + self.session_id)
        self.files_dir = self.session_dir / 'files'
        self.files_dir.mkdir(parents=True, exist_ok=False)
        self.stage = 'opprettet'
        self._log('start', 'Rapportjobb opprettet',
                  job_ids=[str(job.job_id) for job in self.jobs],
                  destination=str(self.directory), formats=list(self.formats))

    def _log(self, event: str, message: str, **fields):
        data = {'timestamp': datetime.now(timezone.utc).isoformat(),
                'event': event, 'stage': self.stage, 'message': message, **fields}
        with self.log_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(data, ensure_ascii=False, default=str) + '\n')
            handle.flush()

    def _progress(self, stage: str, message: str, *, done=0, total=0):
        self.stage = stage
        self._log('status', message, completed=done, total=total)
        if self.on_progress is not None:
            self.on_progress(stage, message, done, total, str(self.log_path))

    def _check_cancel(self):
        if self.cancelled.is_set():
            self._log('stopped', 'Avbrutt av operatør')
            raise ExportStopped('Rapporteksport avbrutt av operatør')

    def _volume_anchors(self, *, include_sources=True):
        unique = {}
        monitored = (*self.work_paths, self.directory) if include_sources else (self.directory,)
        for path in monitored:
            path = path if path.is_absolute() else path.absolute()
            anchor = Path(path.anchor)
            unique[os.path.normcase(str(anchor))] = anchor
        return tuple(unique.values())

    def _probe(self, *, include_sources=True):
        """Return the first unavailable resource, or None if sources look online.

        Merely checking a drive letter is NOT proof that it is the same disk;
        where available, the volume serial must still match the first one.
        """
        if self.probe_override is not None:
            return self.probe_override()
        for anchor in self._volume_anchors(include_sources=include_sources):
            try:
                anchor.stat()
            except OSError as exc:
                return f'Disk/lagringssted {anchor} svarer ikke: {exc}'
            label = os.path.normcase(str(anchor))
            serial = _volume_serial(anchor)
            if serial is not None:
                original = self.identities.get(label)
                if original is not None and original != serial:
                    raise StorageChanged(
                        f'Lagret disk på {anchor} er byttet (volum-ID stemmer ikke). '
                        'Avbryt og kontroller stasjonsbokstav og arbeidsområde.')
                self.identities[label] = serial
        # A previously visible work root should not silently become "no data".
        for path in (self.work_paths if include_sources else ()):
            try:
                is_dir = path.is_dir()
            except OSError:
                is_dir = False
            if is_dir:
                self.seen_work_paths.add(path)
            elif path in self.seen_work_paths:
                return f'Tidligere tilgjengelig arbeidsmappe er borte: {path}'
        return None

    def _wait_until_online(self, reason: str, *, include_sources=True):
        self._progress('venter', 'Venter på disk/arbeidsmappe: ' + str(reason))
        while True:
            self._check_cancel()
            self.cancelled.wait(self.poll_seconds)
            issue = self._probe(include_sources=include_sources)
            if issue is not None:
                continue
            # Require two consecutive successful probes to avoid flapping.
            self.cancelled.wait(min(self.poll_seconds, 1.0))
            self._check_cancel()
            issue = self._probe(include_sources=include_sources)
            if issue is None:
                self._progress('tilkoblet', 'Lagringssted er tilbake; fortsetter trygt.')
                return

    def _source_check(self):
        issue = self._probe()
        if issue is not None:
            raise StorageUnavailable(str(issue))

    def _validate_stage(self):
        """Don't accept a silently incomplete result after a source drop-out."""
        index = self.files_dir / (self.prefix + 'index.json')
        if not index.is_file():
            raise RuntimeError('Felles rapporttjeneste laget ikke kontrollfilen index.json')
        payload = json.loads(index.read_text(encoding='utf-8'))
        results = payload.get('jobs') or []
        if len(results) != len(self.jobs):
            raise RuntimeError('Rapportgrunnlaget har feil antall jobber')
        for job, row in zip(self.jobs, results):
            if str(row.get('job_id')) != str(job.job_id):
                raise RuntimeError('Jobbidentitet skiller seg mellom rapport og jobbliste')
        self._source_check()
        # External adapters deliberately degrade to diagnostics when import
        # folders disappear.  If source files have returned by now, accepting
        # that temporary diagnostic as the final evidential truth is unsafe.
        if 'external' in getattr(self.options, 'enabled', ()):
            for job, row in zip(self.jobs, results):
                ext = row.get('external_evidence') or {}
                diagnostics = ext.get('diagnostics') or []
                failed_to_read = any(
                    ('Ingen tilgjengelig importmappe' in str(msg)
                     or 'Kunne ikke lese importert ekstern evidens' in str(msg))
                    for msg in diagnostics)
                if not failed_to_read:
                    continue
                work_value = (getattr(job, '_effective_work_operations', None)
                              or getattr(job, 'work_operations', None))
                if work_value is None:
                    continue
                work = Path(work_value)
                if any((base / 'external_evidence' / kind).is_dir()
                       for base in (work, work / 'dwm')
                       for kind in ('kdrs_query', 'arkade5')):
                    raise StorageUnavailable(
                        str(job.job_id) + ': eksternt kildegrunnlag kom tilbake '
                        'etter at det var midlertidig utilgjengelig')
        # Some legacy readers turn filesystem I/O into "missing source" and
        # proceed. Re-check those jobs once after the storage health probe.
        # If the depot report is now readable, discard and rebuild the stage.
        for job, row in zip(self.jobs, results):
            if row.get('depot_report'):
                continue
            from .job_summary_a16 import _latest_report
            fresh, _path, _message = _latest_report(job)
            if fresh:
                raise StorageUnavailable(
                    f'{job.job_id}: Depotrapport ble midlertidig utilgjengelig '
                    'under generering; bygger komplett rapport på nytt.')
        self._source_check()

    def _render(self):
        if self.writer is None:
            from .report_service_a20 import write_report_package
            write = write_report_package
        else:
            write = self.writer
        ambiguous = 0
        incomplete = 0
        attempts = 0
        while True:
            self._check_cancel()
            issue = self._probe()
            if issue is not None:
                self._wait_until_online(issue)
            attempts += 1
            self._progress('genererer', f'Bygger lokal rapport, forsøk {attempts}. Ingen nye XPath- eller Arkade-kjøringer.')
            try:
                # A previous interrupted render may have left a subset of
                # artifacts.  Never mix that subset with a new source snapshot.
                for previous in self.files_dir.iterdir():
                    if previous.is_file():
                        previous.unlink()
                # The service uses a nested local temp directory and writes
                # only final artifacts to this *session-owned* local folder.
                write(self.files_dir, self.jobs, self.options, prefix=self.prefix,
                      formats=tuple(dict.fromkeys((*self.formats, 'json'))),
                      overwrite=True, on_warning=self.on_warning)
                self._validate_stage()
                outputs = sorted(p for p in self.files_dir.iterdir()
                                 if p.is_file() and p.suffix.lower() in EXPORT_FORMATS
                                 and p.suffix.lower().lstrip('.') in self.formats)
                if not any(p.name == self.prefix + 'index.' + fmt
                           for fmt in self.formats for p in outputs):
                    raise RuntimeError('Ingen indeksrapport ble generert')
                self._progress('lokal_rapport_klar',
                               f'Komplett lokal rapport klar ({len(outputs)} filer).')
                return outputs
            except ExportStopped:
                raise
            except Exception as exc:
                self._log('build_failed', repr(exc), traceback=traceback.format_exc(),
                          attempt=attempts)
                # Genuine validation/missing file errors are not disk outages.
                issue = self._probe()
                if issue is not None:
                    self._wait_until_online(issue)
                elif isinstance(exc, StorageUnavailable):
                    incomplete += 1
                    if incomplete > 3:
                        raise RuntimeError(
                            'Lagringsstedet er nå tilgjengelig, men rapportgrunnlaget '
                            'var fortsatt ufullstendig etter 3 forsøk. Se lokal logg.') from exc
                    self._progress('nytt_forsok',
                                   'Ufullstendig kildegrunnlag under tidligere forsøk; prøver på nytt.')
                    self.cancelled.wait(self.poll_seconds)
                elif _retryable(exc):
                    self._progress('nytt_forsok', 'Midlertidig lagringsfeil; prøver rapport igjen.')
                    self.cancelled.wait(self.poll_seconds)
                elif isinstance(exc, OSError) and getattr(exc, 'errno', None) == errno.EINVAL and ambiguous < 1:
                    # Errno 22 in the screenshot is ambiguous: one bounded
                    # retry, never an endless "disk disconnected" loop.
                    ambiguous += 1
                    self._progress('nytt_forsok',
                                   '[Errno 22] kan også skyldes filsti/argument. Prøver én gang til og logger feilen.')
                    self.cancelled.wait(self.poll_seconds)
                else:
                    raise

    def _publish_one(self, local: Path, destination: Path):
        self._check_cancel()
        if _same_file(local, destination):
            return 'verified_existing'
        if destination.exists() and not self.overwrite_allowed:
            if self.confirm_overwrite is None:
                raise FileExistsError('Rapportfil finnes allerede: ' + str(destination))
            if not self.confirm_overwrite([str(destination)]):
                raise ExportStopped('Overskriving av rapport er avslått av operatør')
            self.overwrite_allowed = True
            self._log('operator_approved_overwrite', 'Overskriving godkjent av operatør')
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Short temp name also works when the final Windows filename is long.
        pending = destination.parent / ('.dwm-' + self.session_id[-10:] + '.part')
        try:
            with local.open('rb') as src, pending.open('wb') as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            os.replace(pending, destination)
            if not _same_file(local, destination):
                raise OSError(errno.EIO, 'Etterkontroll: resultatfilen er ikke lik den lokale rapporten', str(destination))
            return 'written'
        finally:
            # A write to a detached drive can itself fail here. Do not mask
            # the original exception; left-over .part is harmless and will be
            # overwritten/cleaned on the next successful connection.
            try:
                if pending.exists():
                    pending.unlink()
            except OSError:
                pass

    def _publish(self, outputs: list[Path]) -> Path:
        sent = set()
        ambiguous = 0
        total = len(outputs)
        while len(sent) < total:
            self._check_cancel()
            issue = self._probe(include_sources=False)
            if issue is not None:
                self._wait_until_online(issue, include_sources=False)
            for local in outputs:
                if local.name in sent:
                    continue
                self._check_cancel()
                destination = self.directory / local.name
                self._progress('kopierer',
                               f'Lagrer {len(sent)+1}/{total}: {local.name}',
                               done=len(sent), total=total)
                try:
                    self._publish_one(local, destination)
                    sent.add(local.name)
                    self._log('published', local.name, file=str(destination))
                except ExportStopped:
                    raise
                except Exception as exc:
                    self._log('publish_failed', repr(exc), file=str(destination),
                              traceback=traceback.format_exc())
                    issue = self._probe(include_sources=False)
                    if issue is not None:
                        self._wait_until_online(issue, include_sources=False)
                        break  # resume from the last complete, hashed output
                    if _retryable(exc):
                        self._progress('nytt_forsok',
                                       'Skrivefeil ved publisering. Prøver samme fil på nytt.')
                        self.cancelled.wait(self.poll_seconds)
                        break
                    if isinstance(exc, OSError) and exc.errno == errno.EINVAL and ambiguous < 1:
                        ambiguous += 1
                        self._progress('nytt_forsok',
                                       'Skrivefeil [Errno 22] med tilgjengelig disk: ett nytt forsøk.')
                        self.cancelled.wait(self.poll_seconds)
                        break
                    raise
        for preferred in ('html', 'pdf', 'json', 'csv'):
            chosen = self.directory / (self.prefix + 'index.' + preferred)
            if chosen.name in sent:
                return chosen
        raise RuntimeError('Eksport ferdig, men hovedrapporten mangler')

    def run(self) -> Path:
        try:
            outputs = self._render()
            result = self._publish(outputs)
            self._progress('ferdig', f'Rapport lagret: {result}', done=len(outputs), total=len(outputs))
            self._log('complete', 'Eksport fullført', result=str(result))
            # The durable trace remains local; report copies are in destination.
            shutil.rmtree(self.session_dir, ignore_errors=True)
            return result
        except BaseException as exc:
            self._log('unfinished', repr(exc), traceback=traceback.format_exc(),
                      local_cache=str(self.files_dir))
            raise


def write_reconnectable_report(directory, jobs, options, **kwargs) -> Path:
    """Stable entrypoint for GUI and future unattended batch/report calls."""
    return ReportRecoverySession(directory, jobs, options, **kwargs).run()
