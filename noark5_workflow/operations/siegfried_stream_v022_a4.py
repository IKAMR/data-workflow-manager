"""v0.2.2-a4: bounded and resumable DWM Siegfried execution.

The SIARD Workflow Manager pattern of <=100 explicit paths per sf process is
preserved. All discovery, partial results and checkpoints are Work-local;
Source is exclusively read. No 250,000-file limit and no global file list.

A resumable partial is accepted only for identical Source inventory (path,
size, modification time), Work/job identity and sf executable/signature.
Every committed batch is fsynced before its checkpoint; uncommitted trailing
raw bytes are discarded on a verified resume. Failed runs remain hidden from
completed-run readers until their directory is atomically published.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time
from typing import Callable, Iterable
from uuid import uuid4

from app.siegfried_tool_v0111_a3 import parse_siegfried_json

BATCH_FILES = 100
MAX_COMMAND_CHARS = 20_000  # Windows CreateProcessW safe margin
BATCH_TIMEOUT = 600.0
PROGRESS_INTERVAL = 500
STATE_VERSION = 1
MAX_PARTIAL_CANDIDATES = 50
MAX_RECORD_LINE = 12 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _dump_atomic(path: Path, payload: dict) -> None:
    """Commit a small control file, never half-write it on interruption."""
    fd, temp = tempfile.mkstemp(prefix='.state-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _read_small_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 200_000:
        raise ValueError('Kontrollfilen mangler eller er utrygg: ' + str(path))
    with path.open('r', encoding='utf-8') as handle:
        obj = json.load(handle)
    if not isinstance(obj, dict):
        raise ValueError('Ugyldig kontrollfil: ' + str(path))
    return obj


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _linked(path: Path) -> bool:
    """Do not enter symlinked folders or Windows junctions."""
    return path.is_symlink() or bool(getattr(path, 'is_junction', lambda: False)())


def iter_document_files(source: Path, *, cancelled_cb=None) -> tuple[Iterable[Path], str]:
    """Deterministic, lazy discovery with no file count limit or traversal escape."""
    root = Path(source).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Uttrekksmappen finnes ikke.')
    document_roots = [p for p in root.iterdir()
                      if p.name.casefold() == 'dokument' and not _linked(p) and p.is_dir()]
    scan_roots = sorted(document_roots, key=lambda p: p.name.casefold()) or [root]
    scope = 'DOKUMENT' if document_roots else 'Hele uttrekksmappen (DOKUMENT finnes ikke)'

    def items():
        for scan_root in scan_roots:
            for folder, directories, filenames in os.walk(scan_root, topdown=True, followlinks=False):
                if cancelled_cb is not None and cancelled_cb():
                    raise InterruptedError('Siegfried-skanningen ble avbrutt under filopptelling.')
                here = Path(folder)
                if not here.resolve(strict=True).is_relative_to(root):
                    raise ValueError('Katalog peker utenfor Source: ' + folder)
                directories[:] = sorted((n for n in directories
                                         if not _linked(here / n)), key=str.casefold)
                for name in sorted(filenames, key=str.casefold):
                    path = here / name
                    if _linked(path):
                        continue
                    # Never silently lose a file that disappears during scanning.
                    st = path.stat(follow_symlinks=False)
                    if stat.S_ISREG(st.st_mode):
                        yield path
    return items(), scope


def inventory_files(source: Path, output: Path, *, cancelled_cb=None,
                    progress_cb=None) -> dict:
    """Write one line per discovered file; keep at most a directory's names in RAM."""
    root = Path(source).resolve(strict=True)
    paths, scope = iter_document_files(root, cancelled_cb=cancelled_cb)
    digest = sha256()
    count = 0
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        for path in paths:
            if cancelled_cb is not None and cancelled_cb():
                raise InterruptedError('Siegfried-skanningen ble avbrutt under filopptelling.')
            st = path.stat(follow_symlinks=False)
            if not stat.S_ISREG(st.st_mode) or _linked(path):
                raise ValueError('Kilden ble endret under filopptelling: ' + str(path))
            line = json.dumps({'path': path.relative_to(root).as_posix(),
                               'size': st.st_size, 'mtime_ns': st.st_mtime_ns},
                              ensure_ascii=False, separators=(',', ':')) + '\n'
            digest.update(line.encode('utf-8'))
            stream.write(line)
            count += 1
            if progress_cb is not None and count % PROGRESS_INTERVAL == 0:
                progress_cb(count)
        stream.flush()
        os.fsync(stream.fileno())
    if progress_cb is not None and count % PROGRESS_INTERVAL:
        progress_cb(count)
    return {'inventory_sha256': digest.hexdigest(), 'files_total': count,
            'source_scope': scope}


def _identity(work: Path, job_id: str, job_uid: str) -> tuple[str, str]:
    """A job.json, when present, is authoritative for Work identity."""
    definition = work / 'job.json'
    if not definition.exists():
        return job_id, job_uid
    data = _read_small_json(definition)
    if data.get('file_type') != 'dwm-work-job':
        raise ValueError('Ugyldig Work-jobbidentitet.')
    entry = data.get('job') or {}
    actual_id = str(entry.get('job_id') or data.get('job_id') or '')
    actual_uid = str(data.get('job_uid') or entry.get('job_uid') or '')
    if job_id and actual_id and actual_id != job_id:
        raise ValueError('Valgt Work tilhører en annen jobb-ID.')
    if job_uid and actual_uid and actual_uid != job_uid:
        raise ValueError('Valgt Work tilhører en annen varig jobbidentitet.')
    return actual_id or job_id, actual_uid or job_uid


def _matching_session(session: dict, requested: dict) -> bool:
    return (session.get('state_version') == STATE_VERSION and
            all(session.get(key) == value for key, value in requested.items()) and
            isinstance(session.get('run_id'), str) and
            bool(re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{10}', session['run_id'])))


def _accumulate(summary: dict, batch: list[dict]) -> None:
    """Use the established DWM parser for consistent PUID/multi-match rules."""
    parsed = parse_siegfried_json({'files': batch})
    summary['files_total'] += parsed['files_total']
    for key in ('identified', 'unidentified', 'ambiguous'):
        summary[key] += parsed[key]
    for group in parsed['format_groups']:
        triple = (group['puid'], group['format'], group['version'])
        summary['_groups'][triple] += group['count']


def _new_summary() -> dict:
    return {'files_total': 0, 'identified': 0, 'unidentified': 0,
            'ambiguous': 0, '_groups': Counter()}


def _final_summary(acc: dict) -> dict:
    groups = [{'puid': k[0], 'format': k[1], 'version': k[2], 'count': count}
              for k, count in acc['_groups'].items()]
    groups.sort(key=lambda g: (not bool(g['puid']), g['puid'], g['format'], g['version']))
    return {'files_total': acc['files_total'], 'identified': acc['identified'],
            'unidentified': acc['unidentified'], 'ambiguous': acc['ambiguous'],
            'format_groups': groups}


def _replay(raw: Path, inventory: Path, checkpoint: dict, source: Path) -> dict:
    """Verify hash, offset and every completed filename before trusting a partial."""
    count = checkpoint.get('files_processed')
    size = checkpoint.get('raw_bytes')
    if type(count) is not int or count < 0 or type(size) is not int or size < 0:
        raise ValueError('Ugyldig Siegfried-kontrollpunkt.')
    if raw.is_symlink() or not raw.is_file() or raw.stat().st_size < size:
        raise ValueError('Ufullstendige Siegfried-rådata i kontrollpunkt.')
    digest = sha256()
    summary = _new_summary()
    with raw.open('rb') as records, inventory.open('r', encoding='utf-8') as indexes:
        left = size
        batch = []
        for i in range(count):
            reference = indexes.readline()
            line = records.readline(MAX_RECORD_LINE + 1)
            if not reference or not line or len(line) > MAX_RECORD_LINE or len(line) > left:
                raise ValueError('Siegfried-kontrollpunkt mangler komplette filoppføringer.')
            digest.update(line)
            left -= len(line)
            row = json.loads(line)
            observed = json.loads(reference)
            path = source / Path(observed['path'])
            if (not isinstance(row, dict) or
                os.path.normcase(os.path.normpath(str(row.get('filename') or ''))) !=
                os.path.normcase(os.path.normpath(str(path)))):
                raise ValueError('Siegfried-kontrollpunkt stemmer ikke med kildefilene.')
            batch.append(row)
            if len(batch) == BATCH_FILES:
                _accumulate(summary, batch)
                batch.clear()
        if batch:
            _accumulate(summary, batch)
        if left != 0 or digest.hexdigest() != checkpoint.get('raw_sha256'):
            raise ValueError('Siegfried-kontrollpunkt har ulik SHA-256 eller filgrense.')
    return summary


def _run_sf_batch(executable: str, paths: list[str], *, cancelled_cb=None,
                  timeout: float = BATCH_TIMEOUT) -> list[dict]:
    if not paths:
        return []
    command = [str(executable), '-multi', '64', '-json', *paths]
    # Do not let Windows CreateProcessW hit the 32767-char command line limit.
    if sum(len(x) + 3 for x in command) > MAX_COMMAND_CHARS + 100:
        raise ValueError('For lang kommandolinje for Siegfried-batch.')
    flags = ({'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
             if os.name == 'nt' else {})
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True,
                               encoding='utf-8', errors='replace', **flags)
    started = time.monotonic()
    try:
        while True:
            if cancelled_cb is not None and cancelled_cb():
                raise InterruptedError('Siegfried-kjøringen ble stoppet. Fullførte batcher er bevart.')
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError('Siegfried-batch overskred tidsgrensen på 600 sekunder.')
            try:
                stdout, stderr = process.communicate(timeout=min(0.5, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode != 0:
            raise RuntimeError('Siegfried avsluttet med kode ' + str(process.returncode) +
                               ': ' + str(stderr or '')[:300])
        doc = json.loads(stdout)
        if not isinstance(doc, dict) or not isinstance(doc.get('files'), list):
            raise ValueError('Siegfried returnerte ugyldig JSON.')
        actual = doc['files']
        expected = Counter(os.path.normcase(os.path.normpath(x)) for x in paths)
        found = Counter(os.path.normcase(os.path.normpath(str(x.get('filename') or '')))
                        for x in actual if isinstance(x, dict))
        if expected != found:
            raise RuntimeError('Siegfried returnerte ikke én identifikasjon per forespurt fil.')
        # Check the record structure before writing persistent raw evidence.
        parse_siegfried_json({'files': actual})
        return actual
    finally:
        if process.poll() is None:
            process.kill()
            try:
                process.communicate(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                pass


def _batches(inventory: Path, source: Path, *, skip: int, executable: str):
    """Stream file paths; each command is bounded by count AND length."""
    with inventory.open('r', encoding='utf-8') as handle:
        for _ in range(skip):
            if not handle.readline():
                raise ValueError('Kontrollpunktet overskrider antallet dokumentfiler.')
        batch, chars = [], len(executable) + 30
        for line in handle:
            entry = json.loads(line)
            rel = Path(entry['path'])
            if rel.is_absolute() or '..' in rel.parts or '.' in rel.parts:
                raise ValueError('Utrygg filsti i Siegfried-inventaret.')
            path = source / rel
            name = str(path)
            if len(name) + len(executable) + 40 > MAX_COMMAND_CHARS:
                raise ValueError('Filstien er for lang for Siegfried-CLI: ' + name)
            if batch and (len(batch) >= BATCH_FILES or chars + len(name) + 3 > MAX_COMMAND_CHARS):
                yield batch
                batch, chars = [], len(executable) + 30
            batch.append((path, entry))
            chars += len(name) + 3
        if batch:
            yield batch


def _validate_batch_files(batch: list[tuple[Path, dict]], source: Path) -> list[str]:
    """Detect changed source files before processing them; do not modify Source."""
    paths = []
    for path, expected in batch:
        if _linked(path) or not path.resolve(strict=True).is_relative_to(source):
            raise ValueError('Kildestien har blitt endret eller peker utenfor Source: ' + str(path))
        info = path.stat(follow_symlinks=False)
        if (not stat.S_ISREG(info.st_mode) or info.st_size != expected['size']
                or info.st_mtime_ns != expected['mtime_ns']):
            raise ValueError('Kildedokument endret siden inventaret ble laget: ' + str(path))
        paths.append(str(path))
    return paths


def scan_document_tree(*, source: Path, work: Path, executable: str,
                       version: str, signature: str, job_id: str = '',
                       job_uid: str = '', cancelled_cb=None,
                       log_cb: Callable[[str], None] | None = None,
                       progress_cb: Callable[[int, int], None] | None = None,
                       discovery_cb: Callable[[int], None] | None = None) -> dict:
    """Return completed run paths/model; retain partial results on failure.

    No existing completed run is modified; a matching partial alone may be
    resumed after its inventory AND committed bytes have been verified.
    """
    source = Path(source).resolve(strict=True)
    work = Path(work).resolve(strict=True)
    if source == work or source.is_relative_to(work) or work.is_relative_to(source):
        raise ValueError('Work og Source kan ikke være samme eller overlappende mappe.')
    job_id, job_uid = _identity(work, str(job_id), str(job_uid))
    folder = work / 'external_evidence'
    runs = folder / 'siegfried'
    if _linked(folder) or _linked(runs):
        raise ValueError('Evidensmappen er en symbolsk lenke eller junction.')
    runs.mkdir(parents=True, exist_ok=True)
    discovery = runs / ('.inventory-' + uuid4().hex + '.tmp')
    stage = None
    resumed = False
    processed = 0
    try:
        meta = inventory_files(source, discovery, cancelled_cb=cancelled_cb,
                               progress_cb=discovery_cb)
        if meta['files_total'] == 0:
            raise ValueError('Ingen dokumentfiler funnet for Siegfried. Ingen statistikk er skrevet.')
        match = {'source_root': str(source), 'work_root': str(work),
                 'job_id': job_id, 'job_uid': job_uid,
                 'executable': str(Path(executable).resolve(strict=True)),
                 'version': version, 'signature': signature, **meta}
        previous = sorted((p for p in runs.iterdir()
                           if p.is_dir() and not _linked(p) and p.name.startswith('.partial-')),
                          key=lambda p: p.name, reverse=True)[:MAX_PARTIAL_CANDIDATES]
        summary, checkpoint = None, None
        for candidate in previous:
            try:
                state = _read_small_json(candidate / 'session.json')
                if not _matching_session(state, match) or state['run_id'] != candidate.name[len('.partial-'):]:
                    continue
                cp = _read_small_json(candidate / 'checkpoint.json')
                if (cp.get('run_id') != state['run_id'] or
                    cp.get('inventory_sha256') != meta['inventory_sha256'] or
                    type(cp.get('files_processed')) is not int or
                    cp['files_processed'] > meta['files_total'] or
                    _sha256(candidate / 'file_inventory.jsonl') != meta['inventory_sha256']):
                    continue
                summary = _replay(candidate / 'siegfried_files.jsonl',
                                  candidate / 'file_inventory.jsonl', cp, source)
                stage = candidate
                checkpoint = cp
                resumed = True
                break
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                if log_cb:
                    log_cb('[Siegfried] Eldre ufullstendig batch kunne ikke verifiseres; beholder den urørt.')
                continue
        if stage is None:
            run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:10]
            stage = runs / ('.partial-' + run_id)
            stage.mkdir(exist_ok=False)
            os.replace(discovery, stage / 'file_inventory.jsonl')
            state = {'state_version': STATE_VERSION, 'run_id': run_id,
                     'created_at': _now(), **match}
            _dump_atomic(stage / 'session.json', state)
            (stage / 'siegfried_files.jsonl').touch(exist_ok=False)
            checkpoint = {'state_version': STATE_VERSION, 'run_id': run_id,
                          'inventory_sha256': meta['inventory_sha256'],
                          'files_processed': 0, 'raw_bytes': 0,
                          'raw_sha256': sha256(b'').hexdigest(), 'updated_at': _now()}
            _dump_atomic(stage / 'checkpoint.json', checkpoint)
            summary = _new_summary()
        else:
            discovery.unlink(missing_ok=True)
            run_id = checkpoint['run_id']
            # Only the uncommitted tail may be dropped, after SHA + row verification.
            with (stage / 'siegfried_files.jsonl').open('r+b') as stream:
                stream.truncate(checkpoint['raw_bytes'])
                stream.flush()
                os.fsync(stream.fileno())
        processed = checkpoint['files_processed']
        if log_cb:
            log_cb(f'[Siegfried] {"Gjenopptar" if resumed else "Starter"} {run_id}: '
                   f'{processed} av {meta["files_total"]} filer ferdige. Omfang: {meta["source_scope"]}.')
        if progress_cb:
            progress_cb(processed, meta['files_total'])
        digest = sha256()
        with (stage / 'siegfried_files.jsonl').open('rb') as r:
            for part in iter(lambda: r.read(1024 * 1024), b''):
                digest.update(part)
        if digest.hexdigest() != checkpoint['raw_sha256']:
            raise ValueError('Siegfried-kontrollpunkt har endret råfil. Avbryter for å beskytte evidens.')
        with (stage / 'siegfried_files.jsonl').open('ab') as output:
            for batch in _batches(stage / 'file_inventory.jsonl', source,
                                  skip=processed, executable=executable):
                if cancelled_cb is not None and cancelled_cb():
                    raise InterruptedError('Siegfried-kjøringen er avbrutt; fullførte batcher er bevart.')
                paths = _validate_batch_files(batch, source)
                actual = _run_sf_batch(executable, paths, cancelled_cb=cancelled_cb)
                # One subprocess is an all-or-nothing batch. Write raw before
                # its checkpoint; never announce work not durably persisted.
                payload = b''.join((json.dumps(item, ensure_ascii=False) + '\n').encode('utf-8')
                                   for item in actual)
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
                digest.update(payload)
                _accumulate(summary, actual)
                processed += len(batch)
                checkpoint = {'state_version': STATE_VERSION, 'run_id': run_id,
                              'inventory_sha256': meta['inventory_sha256'],
                              'files_processed': processed,
                              'raw_bytes': output.tell(), 'raw_sha256': digest.hexdigest(),
                              'updated_at': _now()}
                _dump_atomic(stage / 'checkpoint.json', checkpoint)
                if progress_cb:
                    progress_cb(processed, meta['files_total'])
                if log_cb and (processed == meta['files_total'] or
                               (processed // BATCH_FILES) % 100 == 0):
                    log_cb(f'[Siegfried] Kontrollpunkt: {processed} av {meta["files_total"]} filer.')
        if processed != meta['files_total'] or summary['files_total'] != processed:
            raise ValueError('Ufullstendig Siegfried-skanning; samlet resultat blir ikke publisert.')
        model = _final_summary(summary)
        model.update({'format_version': 1,
                      'evidence_type': 'dwm_siegfried_pronom_identification',
                      'source_system': 'DWM / Siegfried', 'run_id': run_id,
                      'created_at': _now(), 'source_scope': meta['source_scope'],
                      'siegfried_version': version, 'siegfried_signature': signature,
                      'raw_evidence': 'siegfried_files.jsonl'})
        _dump_atomic(stage / 'pronom_statistics.json', model)
        manifest = {'file_type': 'dwm-siegfried-run', 'format_version': 1,
                    'run_id': run_id, 'job_id': job_id, 'job_uid': job_uid,
                    'source_root': str(source), 'source_scope': meta['source_scope'],
                    'program': executable, 'program_version': version,
                    'signature': signature, 'raw_file': 'siegfried_files.jsonl',
                    'raw_sha256': digest.hexdigest(),
                    'normalized_file': 'pronom_statistics.json',
                    'files_total': processed, 'created_at': model['created_at'],
                    'inventory_sha256': meta['inventory_sha256'],
                    'batch_files_max': BATCH_FILES, 'resumable_checkpoint': True}
        _dump_atomic(stage / 'manifest.json', manifest)
        target = runs / run_id
        if target.exists():
            raise ValueError('Fullført Siegfried-kjøring finnes allerede: ' + str(target))
        stage.rename(target)
        return {'run_id': run_id, 'target': target, 'model': model,
                'resumed': resumed, 'files_total': processed}
    except Exception as exc:
        # This intentionally retains .partial-* and its verified checkpoint.
        if stage is not None and log_cb:
            log_cb(f'[Siegfried] Stoppet etter {processed} fullførte filer; '
                   f'Work-kontrollpunkt beholdt i {stage}. Årsak: {exc}')
        raise
    finally:
        if discovery.exists():
            discovery.unlink()
