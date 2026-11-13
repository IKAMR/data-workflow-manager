"""Explicit, local, source-linked Noark 5 canonical result snapshot (v1).

This is an additional projection, never a replacement for the individual DWM
master tests, external evidence, the raw event ledger or human assessments.
Nothing is discovered by scanning Source or neighbouring Work directories.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import tempfile
from typing import Any
from uuid import UUID, uuid5

from noark5_workflow.analysis.master_results import load_master_result_set
from noark5_workflow.core.raw_result_store import RawResultStore

SCHEMA_VERSION = '1.0'
FILENAME = 'canonical-results.json'
OUTPUT_SUBDIR = 'noark5_evidence'
NAMESPACE = UUID('a861dc7b-0ed7-4219-b8d0-96b0c9414eaa')
MAX_JSON_SIZE = 100_000_000
MAX_RESOURCES = 100_000


class CanonicalResultError(ValueError):
    """Invalid identity, unsupported evidence or unsafe storage boundary."""


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > MAX_JSON_SIZE:
        raise CanonicalResultError(f'Mangler eller for stor JSON-fil: {path}')
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeError, OSError, json.JSONDecodeError) as exc:
        raise CanonicalResultError(f'Ugyldig JSON i {path}: {exc}') from exc
    if not isinstance(result, dict):
        raise CanonicalResultError(f'Forventer JSON-objekt: {path}')
    return result


def _member(work: Path, candidate: str | Path, *, label: str) -> tuple[Path, str]:
    """Require a pre-existing file owned by the chosen Work, not a Source path."""
    path = Path(candidate)
    path = (path if path.is_absolute() else work / path).resolve()
    try:
        rel = path.relative_to(work.resolve()).as_posix()
    except ValueError as exc:
        raise CanonicalResultError(f'{label} er utenfor valgt Work: {path}') from exc
    if not path.is_file():
        raise CanonicalResultError(f'{label} finnes ikke: {path}')
    return path, rel


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _identifier(*parts: str) -> str:
    return str(uuid5(NAMESPACE, '\u001f'.join(parts)))


def _reference(work: Path, path: Path, rel: str) -> dict[str, str]:
    return {'work_relative_path': rel, 'sha256': _sha(path)}


def _safe_source_label(value: object) -> str | None:
    """Show source XML only when the test names a relative file."""
    if not isinstance(value, str) or not value.strip():
        return None
    if Path(value).is_absolute() or PureWindowsPath(value).is_absolute():
        return None
    return value if len(value) <= 512 else None


def _numeric_values(value: object) -> dict[str, int | float]:
    """Only documented top-level scalar numbers; never infer units or totals."""
    if not isinstance(value, dict):
        return {}
    return {
        str(key): number for key, number in value.items()
        if isinstance(number, (int, float)) and not isinstance(number, bool)
        and not (isinstance(number, float) and (number != number or abs(number) == float('inf')))
    }


def _validate_work(work: Path) -> tuple[Path, dict[str, Any]]:
    work = Path(work).resolve()
    if not work.is_dir():
        raise CanonicalResultError(f'Work er ikke en eksisterende mappe: {work}')
    definition = _load(work / 'job.json')
    if definition.get('file_type') != 'dwm-work-job' or definition.get('format_version') != 1:
        raise CanonicalResultError('Krever autoritativ DWM-jobb i Work (job.json)')
    try:
        uid = str(UUID(str(definition['job_uid'])))
    except (KeyError, ValueError, TypeError) as exc:
        raise CanonicalResultError('Work mangler gyldig varig jobb-ID') from exc
    job = definition.get('job')
    if not isinstance(job, dict):
        raise CanonicalResultError('Work mangler jobbdefinisjon')
    # Same physical directory cannot be both read-only Source and writable Work.
    source = job.get('source_extraction') or job.get('source_root')
    if isinstance(source, str) and source.strip():
        source_path = Path(source)
        if source_path.is_absolute():
            source_path = source_path.resolve()
            if source_path == work or source_path in work.parents or work in source_path.parents:
                raise CanonicalResultError('Work og Source kan ikke overlappe')
    return work, {'job_uid': uid, 'job_id': str(job.get('job_id') or ''), 'source_declared': bool(source)}


def _master_records(work: Path, master_path: Path, rel: str, uid: str) -> tuple[list[dict], dict]:
    master = load_master_result_set(master_path)
    source = master.get('source') or {}
    if source.get('execution_profile') != 'normal':
        raise CanonicalResultError('Kun ordinære individuelle DWM-mastertester er autoritative')
    tests = master.get('tests')
    if not isinstance(tests, list) or len(tests) > MAX_RESOURCES:
        raise CanonicalResultError('Ugyldig eller for stor mastertestliste')
    results: list[dict] = []
    for item in tests:
        if not isinstance(item, dict):
            raise CanonicalResultError('Ugyldig mastertest')
        test_id = str(item.get('test_id') or '')
        if not test_id:
            raise CanonicalResultError('Mastertest mangler test-ID')
        relative_result = item.get('result_file')
        if not relative_result:
            raise CanonicalResultError(f'{test_id}: resultatfil mangler')
        individual, individual_rel = _member(work, master_path.parent / str(relative_result), label=test_id)
        try:
            individual.relative_to(master_path.parent.resolve())
        except ValueError as exc:
            raise CanonicalResultError(f'{test_id}: resultatfil peker utenfor egen kjøring') from exc
        payload = _load(individual)
        if payload.get('test_id') != test_id:
            raise CanonicalResultError(f'{test_id}: resultatfilens test-ID samsvarer ikke')
        status = str(payload.get('status') or item.get('status') or 'unknown')
        available = item.get('availability') == 'available' and status == 'ok' and isinstance(payload.get('values'), dict)
        if available and item.get('role') != 'master':
            raise CanonicalResultError(f'{test_id}: tilgjengelig resultat mangler masterrolle')
        results.append({
            'observation_id': _identifier(uid, 'dwm_master', rel, test_id, individual_rel),
            'source_kind': 'dwm_master',
            'test_id': test_id,
            'run_reference': rel,
            'status': status,
            'availability': 'available' if available else 'unavailable',
            'authoritative_internal_master': bool(available),
            'metadata_id': None,
            'rule_version': None,
            'value_type': 'scalar_numbers' if available and _numeric_values(payload.get('values')) else 'not_materialized',
            'numeric_values': _numeric_values(payload.get('values')) if available else {},
            'metrics_aggregatable': False,  # Counts may overlap between tests.
            'evidence': [_reference(work, individual, individual_rel)],
            'source_xml': _safe_source_label(payload.get('source_xml')),
            'xpath': None,
            'system_id': None,
            'line': None,
        })
    return results, {'source_kind': 'dwm_master', 'reference': _reference(work, master_path, rel), 'execution_profile': 'normal', 'catalog_id': source.get('catalog_id'), 'test_count': len(results)}


def _raw_records(work: Path, raw_path: Path, rel: str, uid: str) -> tuple[list[dict], dict]:
    if raw_path.stat().st_size > MAX_JSON_SIZE:
        raise CanonicalResultError('Råresultatloggen er for stor for a1')
    rows = RawResultStore(raw_path).results()
    if len(rows) > MAX_RESOURCES:
        raise CanonicalResultError('For mange råresultater')
    result = []
    ids = set()
    for entry in rows:
        if not entry.result_id or not entry.test_id or entry.result_id in ids:
            raise CanonicalResultError('Råresultater mangler unik result_id/test_id')
        ids.add(entry.result_id)
        if entry.job_uid and entry.job_uid != uid:
            raise CanonicalResultError('Råresultat tilhører annen Work-jobb')
        # Missing historical UID is retained as unknown, not silently verified.
        result.append({
            'observation_id': _identifier(uid, 'dwm_raw', rel, entry.result_id),
            'source_kind': 'dwm_raw',
            'test_id': entry.test_id,
            'run_reference': entry.run_id or None,
            'status': 'ok' if entry.ok else 'failed',
            'availability': 'available',
            'authoritative_internal_master': False,
            'metadata_id': None,
            'rule_version': entry.definition_version or None,
            'value_type': 'not_materialized',
            'numeric_values': {},
            'metrics_aggregatable': False,
            'evidence': [{'work_relative_path': rel, 'result_id': entry.result_id}],
            'source_xml': None,
            'xpath': None,
            'system_id': None,
            'line': None,
        })
    return result, {'source_kind': 'dwm_raw', 'reference': _reference(work, raw_path, rel), 'result_count': len(result)}


def _external_records(work: Path, bank_path: Path, rel: str, uid: str) -> tuple[list[dict], dict]:
    bank = _load(bank_path)
    if bank.get('format_version') != 2 or not isinstance(bank.get('resources'), list):
        raise CanonicalResultError('Krever resultatbank v2 med resources')
    if len(bank['resources']) > MAX_RESOURCES:
        raise CanonicalResultError('For mange eksterne ressurser')
    result = []
    ids = set()
    for entry in bank['resources']:
        if not isinstance(entry, dict):
            raise CanonicalResultError('Ugyldig ekstern ressurs')
        identity = str(entry.get('resource_id') or '')
        if not identity or identity in ids:
            raise CanonicalResultError('Ekstern ressurs mangler unik resource_id')
        ids.add(identity)
        kind = 'arkade5' if entry.get('source_system') == 'Arkade 5' else 'kdrs_query' if entry.get('source_system') == 'KDRS Query' else 'external_other'
        result.append({
            'observation_id': _identifier(uid, 'external', rel, identity),
            'source_kind': kind,
            'test_id': str(entry.get('test_id') or '') or None,
            'run_reference': str(entry.get('source_import_id') or '') or None,
            'status': str(entry.get('status') or 'unknown'),
            'availability': 'available' if entry.get('has_results') else 'unknown',
            'authoritative_internal_master': False,
            'metadata_id': None,
            'rule_version': None,
            'value_type': 'not_materialized',
            'numeric_values': {},
            'metrics_aggregatable': False,
            'evidence': [{'work_relative_path': rel, 'resource_id': identity}],
            'source_xml': None,
            'xpath': None,
            'system_id': None,
            'line': None,
        })
    return result, {'source_kind': 'external_result_bank', 'reference': _reference(work, bank_path, rel), 'resource_count': len(result)}


def build_canonical_results(
    work_operations: str | Path, *,
    master_paths: tuple[str | Path, ...] = (),
    raw_results_path: str | Path | None = None,
    external_bank_path: str | Path | None = None,
    recorded_at: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Explicit projection from named Work evidence, no recursive discovery.

    Missing sources remain unrepresented rather than being interpreted as 0.
    Existing canonical snapshots are replaced atomically; inputs unchanged.
    """
    work, identity = _validate_work(Path(work_operations))
    entries: list[dict] = []
    sources: list[dict] = []
    used: set[str] = set()
    uid = identity['job_uid']

    for item in master_paths:
        master_file, rel = _member(work, item, label='Masterindeks')
        if rel in used:
            raise CanonicalResultError(f'Duplisert input: {rel}')
        used.add(rel)
        records, source = _master_records(work, master_file, rel, uid)
        entries.extend(records)
        sources.append(source)
    if raw_results_path is not None:
        raw_file, rel = _member(work, raw_results_path, label='Råresultater')
        if rel in used:
            raise CanonicalResultError(f'Duplisert input: {rel}')
        used.add(rel)
        records, source = _raw_records(work, raw_file, rel, uid)
        entries.extend(records)
        sources.append(source)
    if external_bank_path is not None:
        external_file, rel = _member(work, external_bank_path, label='Ekstern resultatbank')
        if rel in used:
            raise CanonicalResultError(f'Duplisert input: {rel}')
        used.add(rel)
        records, source = _external_records(work, external_file, rel, uid)
        entries.extend(records)
        sources.append(source)
    if not used:
        raise CanonicalResultError('Velg minst én eksplisitt resultatkilde i Work')
    if len(entries) > MAX_RESOURCES:
        raise CanonicalResultError('For mange observasjoner')
    identifiers = [entry['observation_id'] for entry in entries]
    if len(set(identifiers)) != len(identifiers):
        raise CanonicalResultError('Dupliserte observasjonsidentiteter')

    document = {
        'schema_version': SCHEMA_VERSION,
        'model_id': 'noark5.canonical-results.v1',
        'profile_id': 'noark5',
        'generated_at': recorded_at or datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'extraction': {
            'stable_id': uid, 'id_type': 'dwm_work_job_uid',
            'job_id_at_generation': identity['job_id'],
            'delivery_id': None, 'noark_version': None, 'system': None,
            'archive_creators': None, 'archive_owner': None,
            'identity_scope': 'work_job_not_verified_source_hash',
        },
        'sources': sources,
        'observations': entries,
        'assessments': [],  # Human assessment ledger stays independent.
        'summary': {
            'observations': len(entries),
            'available_internal_master': sum(x['authoritative_internal_master'] for x in entries),
            'external_observations': sum(x['source_kind'] in ('arkade5', 'kdrs_query', 'external_other') for x in entries),
            'not_aggregated': True,
        },
        'limitations': [
            'No source XML or document binary copied',
            'Statistics, denominators and unknown dimensions not inferred',
            'Overlapping tests/runs not aggregated or deduplicated as events',
            'Technical status does not imply archive acceptance',
        ],
    }
    if write:
        target = work / OUTPUT_SUBDIR / FILENAME
        # Never follow a pre-existing symlink out of this Work on write.
        if target.parent.exists() and target.parent.resolve() != work / OUTPUT_SUBDIR:
            raise CanonicalResultError('Kanonisk resultatmappe peker utenfor valgt Work')
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, tempname = tempfile.mkstemp(prefix='.canonical-', suffix='.tmp', dir=target.parent)
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as stream:
                json.dump(document, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tempname, target)
        finally:
            if os.path.exists(tempname):
                os.unlink(tempname)
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Bygg Noark 5 kanonisk resultatindeks eksplisitt i valgt Work')
    parser.add_argument('--work', type=Path, required=True, help='Eksisterende DWM Work med job.json')
    parser.add_argument('--master', action='append', default=[], help='Sti til master-results.json i Work (gjenta ved behov)')
    parser.add_argument('--raw', help='Sti til raw-results.jsonl i Work')
    parser.add_argument('--external-bank', help='Sti til result-bank.json v2 i Work')
    parser.add_argument('--dry-run', action='store_true', help='Kontroller uten å skrive resultat')
    args = parser.parse_args(argv)
    try:
        data = build_canonical_results(
            args.work, master_paths=tuple(args.master), raw_results_path=args.raw,
            external_bank_path=args.external_bank, write=not args.dry_run,
        )
    except (CanonicalResultError, ValueError, OSError) as exc:
        parser.exit(2, f'FEIL: {exc}\n')
    print(json.dumps({'observations': data['summary']['observations'],
                      'available_internal_master': data['summary']['available_internal_master'],
                      'output': '(dry-run)' if args.dry_run else str(args.work / OUTPUT_SUBDIR / FILENAME)},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
