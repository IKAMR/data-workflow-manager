"""Read-only import inventory per DWM job, without analysis or import.

Presence of an import manifest is not proof that the source test passed.  The
inventory checks referenced files separately and never combines distinct jobs.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from noark5_workflow.core.work_paths import resolve_dwm_work_root
from noark5_workflow.external_evidence.arkade5 import list_arkade5_imports
from noark5_workflow.external_evidence.kdrs_query import list_kdrs_query_imports
from noark5_workflow.external_evidence.arkade5_pronom import (
    load_arkade5_pronom_statistics, summarize_arkade5_pronom_statistics,
)

_TYPES = {'standard': 'Standard', 'u01': 'U1', 'u02': 'U2'}


def _owned_roots(job: Any) -> list[Path]:
    """Try only documented roots belonging to this job, never search other jobs."""
    result: list[Path] = []
    for name in ('_effective_work_operations', 'work_operations'):
        value = getattr(job, name, None)
        if not value:
            continue
        try:
            path = resolve_dwm_work_root(Path(value))
        except (ValueError, TypeError):
            continue
        if path not in result:
            result.append(path)
    return result


def _manifest_issues(root: Path, tool: str, listed: list[dict]) -> list[str]:
    folder = root / 'external_evidence' / tool
    actual = list(folder.glob('*/manifest.json')) if folder.is_dir() else []
    listed_paths = {str(Path(x.get('manifest_path', '')).resolve()) for x in listed if x.get('manifest_path')}
    return [f'Kunne ikke lese manifest: {p}' for p in actual if str(p.resolve()) not in listed_paths]


def _referenced_path(root: Path, ref: str | None) -> Path | None:
    """Accept only references contained in this job's Work area on any OS.

    Windows treats a path beginning with '/' as rooted on the current drive,
    but pathlib.WindowsPath.is_absolute() returns False without a drive.
    Check both path grammars before touching the filesystem.
    """
    if not ref:
        return None
    # Imported relative paths may have been saved with Windows separators.
    value = str(ref).replace('\\', '/')
    if '\x00' in value:
        return None
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if (posix_path.is_absolute() or windows_path.anchor
            or '..' in posix_path.parts):
        return None
    path = root / Path(value)
    try:
        # A manifest cannot escape Work through a symlink/junction either.
        if not path.resolve(strict=False).is_relative_to(root.resolve(strict=False)):
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return path


def _file_ok(root: Path, ref: str | None) -> bool:
    path = _referenced_path(root, ref)
    return bool(path is not None and path.is_file())


def _diagnose_files(root: Path, manifest: dict, *, kind: str) -> list[str]:
    problems = []
    if kind == 'KDRS Query':
        items = manifest.get('files') or []
        if not isinstance(items, list):
            return ['KDRS-manifest har ugyldig filliste']
        if not items:
            return ['KDRS-importen har ingen registrerte resultatfiler']
        for row in items:
            if not isinstance(row, dict):
                problems.append('Ugyldig filpost i KDRS-manifest')
                continue
            if not _file_ok(root, row.get('normalized_file')):
                problems.append('KDRS normalisert fil mangler: ' + str(row.get('normalized_file') or '(ikke oppgitt)'))
            if row.get('preserved_file') and not _file_ok(root, row.get('preserved_file')):
                problems.append('KDRS bevart originalfil mangler: ' + str(row.get('preserved_file')))
    else:
        if not _file_ok(root, manifest.get('normalized_file')):
            problems.append('Arkade normalisert fil mangler: ' + str(manifest.get('normalized_file') or '(ikke oppgitt)'))
        source = manifest.get('source') or {}
        if not isinstance(source, dict):
            source = {}
        if source.get('preserved_file') and not _file_ok(root, source.get('preserved_file')):
            problems.append('Arkade bevart originalfil mangler: ' + str(source.get('preserved_file')))
    return problems


def _select_root(job: Any) -> tuple[Path | None, list[str]]:
    roots = _owned_roots(job)
    if not roots:
        return None, ['Work - operations mangler for jobben']
    scored = []
    for root in roots:
        evidence = root / 'external_evidence'
        score = int((evidence / 'kdrs_query').is_dir()) + int((evidence / 'arkade5').is_dir())
        report = root / 'noark5_reports' / 'depot_validation'
        score += int(report.is_dir())
        scored.append((score, root))
    scored.sort(key=lambda row: -row[0])  # stable: effective root has precedence
    chosen = scored[0][1]
    warnings = []
    if len(roots) > 1 and any(score > 0 and root != chosen for score, root in scored):
        warnings.append('Flere mulige arbeidsområder; viser ett, uten sammenslåing: ' + str(chosen))
    return chosen, warnings


def inspect_job(job: Any) -> dict[str, Any]:
    """Summarize import registrations and file availability for exactly one job."""
    job_id = str(getattr(job, 'job_id', '') or 'Ukjent jobb')
    label = str(getattr(job, 'name', '') or job_id)
    try:
        from noark5_workflow.reporting.depot_metadata import job_display_name
        label = str(job_display_name(job) or label)
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    root, problems = _select_root(job)
    row = {
        'job_id': job_id, 'label': label, 'work': str(root) if root else '',
        'kdrs': {'count': 0, 'types': [], 'imports': []},
        'arkade': {'count': 0, 'imports': []},
        'pronom': {'count': 0, 'files': None, 'unidentified': None, 'imports': []},
        'depot_report': False, 'issues': list(problems),
    }
    if root is None:
        return row
    # List helpers are the same readers used elsewhere in the application.
    try:
        kd = list_kdrs_query_imports(root)
        ar = list_arkade5_imports(root)
    except (OSError, ValueError, TypeError) as exc:
        row['issues'].append('Kunne ikke lese importoversikt: ' + str(exc))
        return row
    row['issues'].extend(_manifest_issues(root, 'kdrs_query', kd))
    row['issues'].extend(_manifest_issues(root, 'arkade5', ar))
    for m in kd:
        types_list = m.get('report_types') or []
        files = m.get('files') or []
        if not isinstance(types_list, list):
            row['issues'].append('KDRS-manifest har ugyldige rapporttyper: ' + str(m.get('import_id')))
            types_list = []
        if not isinstance(files, list):
            files = []
        types = sorted({str(v).lower() for v in types_list}
                       | {str(v.get('report_type') or '').lower() for v in files if isinstance(v, dict)})
        types = [t for t in types if t]
        info = {'import_id': m.get('import_id'), 'date': m.get('imported_at'),
                'types': [_TYPES.get(t, t) for t in types],
                'files': [v.get('original_name') for v in files if isinstance(v, dict)],
                'source': 'KDRS Query'}
        row['kdrs']['imports'].append(info)
        row['kdrs']['types'].extend(info['types'])
        row['issues'].extend(_diagnose_files(root, m, kind='KDRS Query'))
    row['kdrs']['count'] = len(kd)
    row['kdrs']['types'] = [t for t in ('Standard', 'U1', 'U2') if t in row['kdrs']['types']]

    total_pronom_files = 0
    total_unidentified = 0
    for m in ar:
        source = m.get('source') or {}
        if not isinstance(source, dict):
            source = {}
        info = {'import_id': m.get('import_id'), 'date': m.get('imported_at'),
                'test_date': (m.get('source_summary') or {}).get('date_of_testing'),
                'version': m.get('source_version'),
                'files': [source.get('original_name') or source.get('file')],
                'source_sha256': source.get('sha256')}
        row['arkade']['imports'].append(info)
        row['issues'].extend(_diagnose_files(root, m, kind='Arkade 5'))
        evidence = m.get('pronom_evidence') or {}
        if not isinstance(evidence, dict):
            evidence = {}
        stats = evidence.get('statistics') or {}
        if not isinstance(stats, dict):
            row['issues'].append('Arkade-manifest har ugyldig PRONOM-henvisning')
            continue
        if not stats.get('imported'):
            continue
        normalized_path = stats.get('normalized_file')
        if not _file_ok(root, normalized_path):
            row['issues'].append('PRONOM-statistikkfil mangler: ' + str(normalized_path or '(ikke oppgitt)'))
            continue
        if stats.get('preserved_file') and not _file_ok(root, stats.get('preserved_file')):
            row['issues'].append('PRONOM bevart originalfil mangler: ' + str(stats.get('preserved_file')))
        # Existing loader interprets normalized statistics, not the full inventory.
        normalized_manifest = dict(m)
        normalized_manifest['pronom_evidence'] = {
            **evidence,
            'statistics': {**stats, 'normalized_file': str(normalized_path).replace('\\', '/')},
        }
        try:
            norm = load_arkade5_pronom_statistics(root, normalized_manifest)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            norm = None
            row['issues'].append('PRONOM-lesefeil: ' + str(exc))
        if norm is None:
            row['issues'].append('PRONOM-statistikk kan ikke leses: ' + str(normalized_path))
            continue
        try:
            summary = summarize_arkade5_pronom_statistics(norm, manifest=normalized_manifest)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            row['issues'].append('PRONOM-statistikk kan ikke summeres: ' + str(exc))
            continue
        values = summary.get('statistics') or {}
        total_pronom_files += int(values.get('total_files') or 0)
        total_unidentified += int(values.get('unidentified_files') or 0)
        row['pronom']['imports'].append({'import_id': m.get('import_id'),
                                         'date': m.get('imported_at'),
                                         'files': values.get('total_files'),
                                         'unidentified': values.get('unidentified_files'),
                                         'rows': values.get('row_count')})
    row['arkade']['count'] = len(ar)
    row['pronom']['count'] = len(row['pronom']['imports'])
    if row['pronom']['count']:
        # Multiple runs may repeat files. These are occurrence counts, not unique files.
        row['pronom']['files'] = total_pronom_files
        row['pronom']['unidentified'] = total_unidentified
    report_root = root / 'noark5_reports' / 'depot_validation'
    if report_root.is_dir():
        row['depot_report'] = any(report_root.glob(job_id + '__*/depot_validation_report.json'))
    return row


def inspect_jobs(jobs: Any) -> dict[str, Any]:
    rows = []
    for job in jobs:
        try:
            rows.append(inspect_job(job))
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
            rows.append({
                'job_id': str(getattr(job, 'job_id', '?')),
                'label': str(getattr(job, 'name', 'Ukjent uttrekk')), 'work': '',
                'kdrs': {'count': 0, 'types': [], 'imports': []},
                'arkade': {'count': 0, 'imports': []},
                'pronom': {'count': 0, 'files': None, 'unidentified': None, 'imports': []},
                'depot_report': False, 'issues': ['Kunne ikke lese evidensstatus: ' + str(exc)],
            })
    return {
        'jobs': rows, 'count': len(rows),
        'with_kdrs': sum(bool(x['kdrs']['count']) for x in rows),
        'with_arkade': sum(bool(x['arkade']['count']) for x in rows),
        'with_pronom': sum(bool(x['pronom']['count']) for x in rows),
        'with_report': sum(x['depot_report'] for x in rows),
        'with_issues': sum(bool(x['issues']) for x in rows),
        'note': ('Import registrert betyr ikke at testene er bestått. PRONOM-filtall fra flere '
                 'kjøringer er ikke antall unike dokumenter.'),
    }
