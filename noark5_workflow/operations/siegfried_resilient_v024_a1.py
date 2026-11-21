"""Resilient Siegfried batch adapter for DWM v0.2.4-a1.

This is an additive scanner using the established a4 inventory/checkpoint and
source-validation machinery. Only malformed or inconsistent sf JSON is
recoverable: the batch is retried, split and finally represented by an
explicit per-file error. Missing sources, cancellation, timeout, changed
source identity, storage failure and non-zero sf exit are still fatal.

All original sf failure responses go to Work diagnostics, never Source.
Partial runs are not published as completed runs. A completed scan may include
per-file errors, explicitly counted in summary and manifest.
"""
from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Event
from typing import Callable
import json
import os
import re
import subprocess
import time
from uuid import uuid4

from app.siegfried_tool_v0111_a3 import parse_siegfried_json
from . import siegfried_stream_v022_a4 as base

ERROR_CODE = 'DWM_SIEGFRIED_INVALID_JSON'
# Existing a4/a5 tests patch the legacy subprocess boundary on Windows.
# Preserve that test seam; production always executes _parse_sf below.
_BASE_BATCH_FUNCTION = base._run_sf_batch


class BadSiegfriedResponse(ValueError):
    def __init__(self, reason: str, stdout: bytes, stderr: bytes):
        super().__init__(reason)
        self.reason = reason
        self.stdout = stdout
        self.stderr = stderr


@dataclass(frozen=True)
class RawProblem:
    paths: tuple[str, ...]
    reason: str
    stdout: bytes
    stderr: bytes
    attempt: int


def _parse_sf(executable: str, paths: list[str], *, cancelled_cb=None,
              timeout: float | None = None) -> list[dict]:
    """Run sf with byte-preserving stdout; never 'repair' invalid escapes."""
    if not paths:
        return []
    command = [str(executable), '-multi', '64', '-json', *paths]
    if sum(len(piece) + 3 for piece in command) > base.MAX_COMMAND_CHARS + 100:
        raise ValueError('For lang kommandolinje for Siegfried-batch.')
    flags = ({'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
             if os.name == 'nt' else {})
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, **flags)
    started = time.monotonic()
    try:
        while True:
            if cancelled_cb is not None and cancelled_cb():
                raise InterruptedError('Siegfried-kjøringen ble avbrutt; kontrollpunkter er bevart.')
            remain = (base.BATCH_TIMEOUT if timeout is None else timeout) - (time.monotonic() - started)
            if remain <= 0:
                raise TimeoutError('Siegfried-batch overskred tidsgrensen.')
            try:
                stdout, stderr = process.communicate(timeout=min(.5, remain))
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode != 0:
            detail = (stderr or b'').decode('utf-8', errors='replace')[:300]
            raise RuntimeError(f'Siegfried avsluttet med kode {process.returncode}: {detail}')
        try:
            document = json.loads(stdout)
        except (ValueError, UnicodeDecodeError) as exc:
            raise BadSiegfriedResponse(f'Ugyldig Siegfried-JSON: {exc}', stdout, stderr) from exc
        if not isinstance(document, dict) or not isinstance(document.get('files'), list):
            raise BadSiegfriedResponse('Siegfried svarte uten et files-array.', stdout, stderr)
        actual = document['files']
        expected = [os.path.normcase(os.path.normpath(p)) for p in paths]
        observed = [os.path.normcase(os.path.normpath(str(row.get('filename') or '')))
                    for row in actual if isinstance(row, dict)]
        if len(actual) != len(paths) or sorted(expected) != sorted(observed):
            raise BadSiegfriedResponse('Siegfried svarte med feil filantall eller filidentitet.', stdout, stderr)
        try:
            parse_siegfried_json({'files': actual})
        except (ValueError, TypeError) as exc:
            raise BadSiegfriedResponse(f'Feil i Siegfried-resultatstrukturen: {exc}', stdout, stderr) from exc
        return actual
    finally:
        if process.poll() is None:
            process.kill()
            try:
                process.communicate(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                pass


def _run_sf(executable: str, paths: list[str], *, cancelled_cb=None):
    if base._run_sf_batch is not _BASE_BATCH_FUNCTION:
        return base._run_sf_batch(executable, paths, cancelled_cb=cancelled_cb)
    return _parse_sf(executable, paths, cancelled_cb=cancelled_cb)


def _recover_batch(batch: list[tuple[Path, dict]], source: Path, executable: str,
                   *, cancelled_cb=None, depth: int = 0) -> tuple[list[dict], list[RawProblem]]:
    """Bounded retry + binary isolation. Never synthesize a successful PUID."""
    if cancelled_cb is not None and cancelled_cb():
        raise InterruptedError('Siegfried-kjøringen ble avbrutt; kontrollpunkter er bevart.')
    paths = base._validate_batch_files(batch, source)
    errors: list[RawProblem] = []
    tries = 2 if depth == 0 or len(batch) == 1 else 1
    last = None
    for attempt in range(1, tries + 1):
        try:
            rows = _run_sf(executable, paths, cancelled_cb=cancelled_cb)
            return base._source_order_rows(batch, rows), errors
        except BadSiegfriedResponse as exc:
            last = exc
            errors.append(RawProblem(tuple(paths), str(exc), exc.stdout, exc.stderr, attempt))
    if len(batch) > 1:
        mid = len(batch) // 2
        left, problems_left = _recover_batch(batch[:mid], source, executable,
                                             cancelled_cb=cancelled_cb, depth=depth+1)
        right, problems_right = _recover_batch(batch[mid:], source, executable,
                                               cancelled_cb=cancelled_cb, depth=depth+1)
        return left + right, errors + problems_left + problems_right
    # Explicitly distinguish a failed identification from an unidentified file.
    return ([{'filename': paths[0], 'matches': [],
              'errors': f'{ERROR_CODE}: {last}',
              'dwm_identification_status': 'error'}], errors)


def _ordered_recovery_batches(batches, source: Path, executable: str, *,
                              workers: int, cancelled_cb=None):
    """Only owner thread receives and persists records, in inventory order."""
    if type(workers) is not int or not 1 <= workers <= base.MAX_SF_WORKERS:
        raise ValueError(f'Ugyldig Siegfried-prosessantall (1-{base.MAX_SF_WORKERS}).')
    if workers == 1:
        for batch in batches:
            yield batch, *_recover_batch(batch, source, executable, cancelled_cb=cancelled_cb)
        return
    stop = Event()
    iterator = iter(batches)
    waiting = deque()

    def cancelled():
        return stop.is_set() or (cancelled_cb is not None and cancelled_cb())

    def identify(batch):
        return _recover_batch(batch, source, executable, cancelled_cb=cancelled)

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='dwm-sf') as pool:
        try:
            def submit():
                if cancelled():
                    raise InterruptedError('Siegfried-kjøringen ble avbrutt.')
                try:
                    batch = next(iterator)
                except StopIteration:
                    return False
                waiting.append((batch, pool.submit(identify, batch)))
                return True

            for _ in range(workers):
                if not submit():
                    break
            while waiting:
                if cancelled():
                    raise InterruptedError('Siegfried-kjøringen ble avbrutt.')
                batch, future = waiting.popleft()
                rows, problems = future.result()
                if cancelled():
                    raise InterruptedError('Siegfried-kjøringen ble avbrutt.')
                yield batch, rows, problems
                submit()
        finally:
            stop.set()
            for _batch, future in waiting:
                future.cancel()


def _persist_diagnostics(stage: Path, problems: list[RawProblem], *,
                         start_index: int, log_cb=None) -> None:
    if not problems:
        return
    root = stage / 'diagnostics'
    if root.is_symlink():
        raise ValueError('Siegfried-diagnostikkmappen kan ikke være lenke.')
    root.mkdir(exist_ok=True)
    index = root / 'index.jsonl'
    if index.is_symlink():
        raise ValueError('Siegfried-diagnostikkindeks kan ikke være lenke.')
    with index.open('ab') as handle:
        for position, problem in enumerate(problems):
            # Random suffix prevents accidentally overwriting older diagnostics
            # after resume; every byte from the failed response is preserved.
            key = f'{start_index:012d}-{position:03d}-{uuid4().hex[:10]}'
            out_file = root / (key + '.stdout')
            err_file = root / (key + '.stderr')
            out_file.write_bytes(problem.stdout)
            err_file.write_bytes(problem.stderr)
            record = {
                'format_version': 1, 'timestamp_utc': base._now(),
                'batch_offset': start_index, 'file_paths': list(problem.paths),
                'attempt': problem.attempt, 'reason': problem.reason,
                'stdout_file': out_file.name,
                'stdout_bytes': len(problem.stdout),
                'stdout_sha256': sha256(problem.stdout).hexdigest(),
                'stderr_file': err_file.name,
                'stderr_bytes': len(problem.stderr),
                'stderr_sha256': sha256(problem.stderr).hexdigest(),
            }
            handle.write((json.dumps(record, ensure_ascii=False, sort_keys=True)+'\n').encode('utf-8'))
        handle.flush()
        os.fsync(handle.fileno())
    if log_cb is not None:
        log_cb(f'[Siegfried] Ugyldig svar forsøkt isolert; {len(problems)} rårespons(er) bevart i {root}.')


def _diagnostic_count(index: Path) -> int:
    if not index.is_file():
        return 0
    with index.open('rb') as stream:
        return sum(1 for line in stream if line.strip())


def _failure_count(raw: Path) -> int:
    count = 0
    with raw.open('rb') as reader:
        for line in reader:
            record = json.loads(line)
            if record.get('dwm_identification_status') == 'error':
                count += 1
    return count


def scan_document_tree(*, source: Path, work: Path, executable: str,
                       version: str, signature: str, job_id: str = '',
                       job_uid: str = '', cancelled_cb=None,
                       log_cb: Callable[[str], None] | None = None,
                       progress_cb: Callable[[int, int], None] | None = None,
                       discovery_cb: Callable[[int], None] | None = None,
                       workers: int = 1) -> dict:
    """Compatible a4/a5 checkpointing plus recoverable malformed sf responses."""
    if type(workers) is not int or not 1 <= workers <= base.MAX_SF_WORKERS:
        raise ValueError('Ugyldig antall Siegfried-prosesser.')
    source = Path(source).resolve(strict=True)
    work = Path(work).resolve(strict=True)
    if source == work or source.is_relative_to(work) or work.is_relative_to(source):
        raise ValueError('Work og Source kan ikke være samme eller overlappende mappe.')
    job_id, job_uid = base._identity(work, str(job_id), str(job_uid))
    runs = work / 'external_evidence' / 'siegfried'
    if base._linked(runs) or base._linked(runs.parent):
        raise ValueError('Evidensmappen er en symbolsk lenke eller junction.')
    runs.mkdir(parents=True, exist_ok=True)
    discovery = runs / ('.inventory-' + uuid4().hex + '.tmp')
    stage = None
    resumed = False
    processed = 0
    try:
        meta = base.inventory_files(source, discovery, cancelled_cb=cancelled_cb,
                                    progress_cb=discovery_cb)
        if not meta['files_total']:
            raise ValueError('Ingen dokumentfiler funnet for Siegfried.')
        request = {'source_root': str(source), 'work_root': str(work),
                   'job_id': job_id, 'job_uid': job_uid,
                   'executable': str(Path(executable).resolve(strict=True)),
                   'version': version, 'signature': signature, **meta}
        candidates = sorted((p for p in runs.iterdir() if p.is_dir() and
                             not base._linked(p) and p.name.startswith('.partial-')),
                            key=lambda p: p.name, reverse=True)[:base.MAX_PARTIAL_CANDIDATES]
        summary = checkpoint = None
        for candidate in candidates:
            try:
                state = base._read_small_json(candidate / 'session.json')
                if not base._matching_session(state, request) or (
                        state['run_id'] != candidate.name[len('.partial-'):]):
                    continue
                cp = base._read_small_json(candidate / 'checkpoint.json')
                if (cp.get('run_id') != state['run_id'] or
                    cp.get('inventory_sha256') != meta['inventory_sha256'] or
                    type(cp.get('files_processed')) is not int or
                    cp['files_processed'] > meta['files_total'] or
                    base._sha256(candidate / 'file_inventory.jsonl') != meta['inventory_sha256']):
                    continue
                summary = base._replay(candidate / 'siegfried_files.jsonl',
                                       candidate / 'file_inventory.jsonl', cp, source)
                stage, checkpoint, resumed = candidate, cp, True
                break
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                if log_cb:
                    log_cb('[Siegfried] Eldre kontrollpunkt er ikke verifisert; beholdes urørt.')
        if stage is None:
            run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:10]
            stage = runs / ('.partial-' + run_id)
            stage.mkdir(exist_ok=False)
            os.replace(discovery, stage / 'file_inventory.jsonl')
            base._dump_atomic(stage / 'session.json', {
                'state_version': base.STATE_VERSION, 'run_id': run_id,
                'created_at': base._now(), **request})
            (stage / 'siegfried_files.jsonl').touch(exist_ok=False)
            checkpoint = {'state_version': base.STATE_VERSION, 'run_id': run_id,
                          'inventory_sha256': meta['inventory_sha256'],
                          'files_processed': 0, 'raw_bytes': 0,
                          'raw_sha256': sha256(b'').hexdigest(), 'updated_at': base._now()}
            base._dump_atomic(stage / 'checkpoint.json', checkpoint)
            summary = base._new_summary()
        else:
            discovery.unlink(missing_ok=True)
            run_id = checkpoint['run_id']
            with (stage / 'siegfried_files.jsonl').open('r+b') as stream:
                stream.truncate(checkpoint['raw_bytes'])
                stream.flush()
                os.fsync(stream.fileno())
        processed = checkpoint['files_processed']
        if log_cb:
            log_cb(f'[Siegfried] {"Gjenopptar" if resumed else "Starter"} {run_id}: '
                   f'{processed} av {meta["files_total"]} filer. {workers} sf-prosesser.')
        if progress_cb:
            progress_cb(processed, meta['files_total'])
        digest = sha256()
        with (stage / 'siegfried_files.jsonl').open('rb') as reader:
            for part in iter(lambda: reader.read(1024*1024), b''):
                digest.update(part)
        if digest.hexdigest() != checkpoint['raw_sha256']:
            raise ValueError('Siegfried-kontrollpunkt har endret råfil.')
        batches = _ordered_recovery_batches(
            base._batches(stage / 'file_inventory.jsonl', source,
                          skip=processed, executable=executable),
            source, executable, workers=workers, cancelled_cb=cancelled_cb)
        try:
            with (stage / 'siegfried_files.jsonl').open('ab') as output:
                for batch, rows, problems in batches:
                    if cancelled_cb is not None and cancelled_cb():
                        raise InterruptedError('Siegfried-kjøringen er avbrutt.')
                    _persist_diagnostics(stage, problems, start_index=processed, log_cb=log_cb)
                    payload = b''.join((json.dumps(row, ensure_ascii=False) + '\n').encode('utf-8')
                                       for row in rows)
                    output.write(payload)
                    output.flush()
                    os.fsync(output.fileno())
                    digest.update(payload)
                    base._accumulate(summary, rows)
                    processed += len(batch)
                    checkpoint = {'state_version': base.STATE_VERSION, 'run_id': run_id,
                                  'inventory_sha256': meta['inventory_sha256'],
                                  'files_processed': processed,
                                  'raw_bytes': output.tell(),
                                  'raw_sha256': digest.hexdigest(),
                                  'updated_at': base._now()}
                    base._dump_atomic(stage / 'checkpoint.json', checkpoint)
                    if progress_cb:
                        progress_cb(processed, meta['files_total'])
                    if log_cb and (problems or processed == meta['files_total'] or
                                   processed % 10_000 == 0):
                        log_cb(f'[Siegfried] Kontrollpunkt: {processed} av {meta["files_total"]} filer.')
        finally:
            batches.close()
        if processed != meta['files_total'] or summary['files_total'] != processed:
            raise ValueError('Ufullstendig Siegfried-skanning; ingen fullstendig rapport publiseres.')
        failed = _failure_count(stage / 'siegfried_files.jsonl')
        model = base._final_summary(summary)
        model['unidentified'] = max(0, model['unidentified'] - failed)
        model['files_failed'] = failed
        index = stage / 'diagnostics' / 'index.jsonl'
        response_errors = _diagnostic_count(index)
        model['json_response_errors'] = response_errors
        model['identification_status'] = ('complete_with_file_errors' if failed else 'complete')
        model.update({'format_version': 1,
                      'evidence_type': 'dwm_siegfried_pronom_identification',
                      'source_system': 'DWM / Siegfried', 'run_id': run_id,
                      'created_at': base._now(), 'source_scope': meta['source_scope'],
                      'siegfried_version': version, 'siegfried_signature': signature,
                      'raw_evidence': 'siegfried_files.jsonl'})
        base._dump_atomic(stage / 'pronom_statistics.json', model)
        manifest = {'file_type': 'dwm-siegfried-run', 'format_version': 1,
                    'run_id': run_id, 'job_id': job_id, 'job_uid': job_uid,
                    'source_root': str(source), 'source_scope': meta['source_scope'],
                    'program': executable, 'program_version': version,
                    'signature': signature, 'raw_file': 'siegfried_files.jsonl',
                    'raw_sha256': digest.hexdigest(),
                    'normalized_file': 'pronom_statistics.json',
                    'files_total': processed, 'files_failed': failed,
                    'json_response_errors': response_errors,
                    'identification_status': model['identification_status'],
                    'created_at': model['created_at'],
                    'inventory_sha256': meta['inventory_sha256'],
                    'batch_files_max': base.BATCH_FILES, 'resumable_checkpoint': True,
                    'siegfried_process_workers': workers}
        if index.exists():
            manifest['diagnostics_index'] = 'diagnostics/index.jsonl'
            manifest['diagnostics_index_sha256'] = base._sha256(index)
        base._dump_atomic(stage / 'manifest.json', manifest)
        target = runs / run_id
        if target.exists():
            raise ValueError('Fullført Siegfried-kjøring finnes allerede: ' + str(target))
        stage.rename(target)
        return {'run_id': run_id, 'target': target, 'model': model,
                'resumed': resumed, 'files_total': processed}
    except Exception as exc:
        if stage is not None and log_cb is not None:
            log_cb(f'[Siegfried] Stoppet etter {processed} fullførte filer; '
                   f'kontrollpunktet er bevart i {stage}. Årsak: {exc}')
        raise
    finally:
        if discovery.exists():
            discovery.unlink()
