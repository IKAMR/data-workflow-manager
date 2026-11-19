"""Opt-in, non-authoritative external result extraction for a selected DWM Work.

Preserves source language and raw statuses; never infers pass/fail, applicability,
completeness, acceptance or an Arkade schema not actually present in the file.
The separate analysis is *not* a replacement for canonical-results.json.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import tempfile
from typing import Any

MODEL = 'noark5.external-analysis.v1'
OUT = 'noark5_evidence/canonical-external-analysis.json'
# Native Siegfried is streamed; normalized JSON is decoded as one document.
MAX_SOURCE_STREAM = 512 * 1024 * 1024
MAX_SOURCE_NORMALIZED = 48 * 1024 * 1024
MAX_CANONICAL_REFERENCE = 100_000_000
MAX_ANALYSIS_OUTPUT = 64 * 1024 * 1024
MAX_FILES = 100
MAX_ITEMS = 100_000
MAX_TOTAL_ITEMS = 200_000
MAX_ELEMENT = 2 * 1024 * 1024

class ExternalImportError(ValueError):
    pass


def _is_normalized_json(relative: str) -> bool:
    name = relative.lower()
    return (name.endswith('/normalized/arkade5_results.json') or
            name.endswith('/pronom_statistics.json'))


def _inside(work: Path, source: str | Path) -> tuple[Path, str]:
    s = str(source)
    if PureWindowsPath(s).is_absolute() and os.name != 'nt':
        raise ExternalImportError('Windows-sti kan ikke tolkes paa denne plattformen')
    candidate = Path(source)
    candidate = candidate if candidate.is_absolute() else work / candidate
    part = candidate
    while part != work and part != part.parent:
        if part.is_symlink():
            raise ExternalImportError('Symbolsk lenke er ikke tillatt som kilde')
        part = part.parent
    candidate = candidate.resolve()
    root = work.resolve()
    try:
        relative = candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise ExternalImportError('Ekstern kilde ligger utenfor valgt Work') from exc
    if not relative or relative == OUT or relative.startswith('noark5_evidence/'):
        raise ExternalImportError('Velg en opprinnelig ekstern resultatfil, ikke en DWM-indeks')
    if not candidate.is_file() or candidate.is_symlink():
        raise ExternalImportError('Valgt kildefil finnes ikke')
    size = candidate.stat().st_size
    limit = (MAX_SOURCE_NORMALIZED if _is_normalized_json(relative) or
             candidate.suffix.lower() != '.json' else MAX_SOURCE_STREAM)
    if size > limit:
        raise ExternalImportError(f'Ekstern kilde {relative}: {size} bytes '
                                  f'({size / 1048576:.1f} MiB) overstiger kildegrensen '
                                  f'{limit} bytes ({limit / 1048576:.1f} MiB). '
                                  'Velg en mindre, fullstendig resultatfil.')
    return candidate, relative


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'), parse_constant=_invalid_json_constant)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ExternalImportError(f'Ugyldig JSON i {path.name}: {exc}') from exc


def _invalid_json_constant(value: str):
    raise ValueError(f'Ikke-standard JSON-verdi: {value}')


def _arkade_entries(doc: Any, relative: str) -> dict[str, Any]:
    """Recognize only explicit test/result records, preserve native text status.

    This is a conservative adapter for a *normalized* list of records, not the
    Arkade 5 native XML schema. No status vocabulary is assumed. A record with
    missing ID or status makes the entire structure unrecognized.
    """
    if not relative.lower().endswith('/normalized/arkade5_results.json'):
        return {'source_format': 'unknown', 'interpretation': 'not_parsed',
                'reason': 'Ingen bekreftet Arkade-resultatstruktur for valgt fil'}
    if not isinstance(doc, dict):
        return {'source_format': 'arkade_normalized_candidate', 'interpretation': 'not_parsed',
                'reason': 'Forventer JSON-objekt'}
    key = 'tests' if isinstance(doc.get('tests'), list) else 'results' if isinstance(doc.get('results'), list) else None
    if key is None:
        return {'source_format': 'arkade_normalized_candidate', 'interpretation': 'not_parsed',
                'reason': 'Fant ikke eksplisitt tests/results-liste; trenger ekte eksempel'}
    entries = doc[key]
    if len(entries) > MAX_ITEMS:
        raise ExternalImportError('For mange testposter')
    # DWM's normalized Arkade v2 report has a typed envelope and source_status.
    # Other normalized records continue to be accepted as opaque source status text.
    is_dwm_report = (doc.get('format_version') == 2 and
                     doc.get('evidence_type') == 'external_validation_report' and
                     doc.get('source_system') == 'Arkade 5')
    records = []
    for i, entry in enumerate(entries):
        if len(json.dumps(entry, ensure_ascii=False).encode('utf-8')) > MAX_ELEMENT:
            raise ExternalImportError(f'Arkade testpost {i} overstiger {MAX_ELEMENT} bytes')
        if not isinstance(entry, dict):
            return {'source_format': 'arkade_normalized_candidate', 'interpretation': 'not_parsed',
                    'reason': 'Testposter er ikke objekter'}
        identifier = entry.get('test_id', entry.get('id'))
        status = entry.get('source_status') if is_dwm_report else entry.get('status')
        if not isinstance(identifier, str) or not identifier.strip() or not isinstance(status, str) or not status.strip():
            return {'source_format': 'arkade_normalized_candidate', 'interpretation': 'not_parsed',
                    'reason': 'Hver post maa inneholde tekstfeltene test_id/id og status'}
        if len(identifier) > 300 or len(status) > 120:
            raise ExternalImportError('Ugyldig lang testidentifikator eller status')
        record = {'index': i, 'external_test_id': identifier, 'reported_status': status,
                  'status_interpretation': 'source_text_not_mapped',
                  'technical_verification': 'not_verified', 'depot_approval': None}
        if is_dwm_report:
            result_entries = entry.get('results')
            count = entry.get('number_of_errors')
            if (not isinstance(result_entries, list) or len(result_entries) > MAX_ITEMS
                    or type(count) is not int or count < 0):
                return {'source_format': 'arkade_normalized_v2', 'interpretation': 'not_parsed',
                        'reason': 'Ugyldig resultatliste eller feiltall i Arkade v2'}
            counts = {'Success': 0, 'Error': 0, 'Warning': 0, 'Other': 0}
            issues = []
            for j, item in enumerate(result_entries):
                if not isinstance(item, dict):
                    return {'source_format': 'arkade_normalized_v2', 'interpretation': 'not_parsed',
                            'reason': 'Ugyldig resultatpost i Arkade v2'}
                kind = item.get('result_type')
                counts[kind if kind in counts else 'Other'] += 1
                if kind in ('Error', 'Warning'):
                    issues.append({'index': j, 'result_type': kind,
                                   'message': item.get('message') if isinstance(item.get('message'), str) else None,
                                   'result_set_path': item.get('result_set_path') if isinstance(item.get('result_set_path'), list) else [],
                                   'location': item.get('location') if isinstance(item.get('location'), dict) else None})
            record.update({'test_name': entry.get('test_name'), 'test_type': entry.get('test_type'),
                           'source_number_of_errors': count,
                           'reported_result_counts': counts, 'reported_issues': issues})
        records.append(record)
    response = {'source_format': 'arkade_normalized_v2' if is_dwm_report else 'arkade_normalized_candidate',
            'interpretation': 'reported_test_records_unverified',
            'record_count': len(records), 'records': records,
            'note': 'Status er gjengitt ordrett. Arkade-resultater er ekstern evidens, ikke depotaksept.'}
    if is_dwm_report:
        response['source_version'] = doc.get('source_version')
        response['reported_summary'] = {k: doc.get('summary', {}).get(k) for k in (
            'number_of_tests_run', 'number_of_errors', 'number_of_warnings',
            'archive_type', 'system_name', 'archival_period')}
        response['reported_status_counts'] = {key: sum(r['reported_status'] == key for r in records)
                                              for key in sorted({r['reported_status'] for r in records})}
    return response


def _pronom_statistics(doc: Any, relative: str) -> dict[str, Any] | None:
    if not relative.lower().endswith('/normalized/pronom_statistics.json'):
        return None
    if not (isinstance(doc, dict) and doc.get('format_version') == 1 and
            doc.get('evidence_type') == 'arkade5_pronom_format_statistics' and
            doc.get('source_system') == 'Arkade 5'):
        return None
    csv = doc.get('csv')
    if not isinstance(csv, dict) or not isinstance(csv.get('rows'), list):
        return {'source_format': 'arkade_pronom_statistics_v1', 'interpretation': 'not_parsed',
                'reason': 'Mangler rader i PRONOM-statistikk'}
    rows = csv['rows']
    if len(rows) > MAX_ITEMS:
        raise ExternalImportError('For mange formatrader')
    output = []
    total = 0
    for row in rows:
        if len(json.dumps(row, ensure_ascii=False).encode('utf-8')) > MAX_ELEMENT:
            raise ExternalImportError(f'PRONOM formatrad overstiger {MAX_ELEMENT} bytes')
        if not isinstance(row, dict) or not all(k in row for k in ('Format-ID', 'Filtype', 'Formatversjon', 'RAF-220301', 'Antall')):
            return {'source_format': 'arkade_pronom_statistics_v1', 'interpretation': 'not_parsed',
                    'reason': 'Ukjente PRONOM-felt'}
        try:
            count = int(row['Antall'])
        except (ValueError, TypeError):
            count = -1
        if count < 0 or count > 100_000_000:
            return {'source_format': 'arkade_pronom_statistics_v1', 'interpretation': 'not_parsed',
                    'reason': 'Ugyldig Antall-verdi'}
        total += count
        output.append({'pronom_id': row['Format-ID'], 'format_name': row['Filtype'],
                       'format_version': row['Formatversjon'], 'reported_raf_220301': row['RAF-220301'],
                       'reported_file_count': count})
    return {'source_format': 'arkade_pronom_statistics_v1', 'interpretation': 'format_statistics_only',
            'record_count': 0, 'format_rows': len(output), 'reported_total_files': total,
            'formats': output, 'technical_verification': 'not_verified', 'depot_approval': None,
            'note': 'RAF-220301 er en kildeverdi fra Arkade, ikke en godkjenning i DWM.'}


def inspect_selected_external(path: Path, relative: str) -> dict[str, Any]:
    if path.suffix.lower() != '.json':
        return {'source_format': 'unknown', 'interpretation': 'not_parsed',
                'reason': 'Filtypen er ikke stoettet av a10-adapteren'}
    if not _is_normalized_json(relative):
        from noark5_workflow.analysis.streaming_siegfried import inspect_siegfried_stream
        try:
            siegfried = inspect_siegfried_stream(path)
        except (OSError, UnicodeError, ValueError) as exc:
            raise ExternalImportError(f'Ekstern kilde {relative}: {exc}') from exc
        if siegfried.get('format') == 'siegfried_json':
            return {'source_format': 'siegfried_json', **{k: v for k, v in siegfried.items() if k != 'format'}}
        return {'source_format': 'unknown', 'interpretation': 'not_parsed',
                'reason': 'Ingen bekreftet ekstern resultatstruktur for valgt fil'}
    try:
        doc = _json(path)
    except ExternalImportError as exc:
        raise ExternalImportError(f'Ekstern kilde {relative}: {exc}') from exc
    if (isinstance(doc, dict) and doc.get('evidence_type') == 'dwm_siegfried_pronom_identification'):
        from noark5_workflow.analysis.siegfried_statistics import summarize_dwm_siegfried_statistics
        try:
            summary = summarize_dwm_siegfried_statistics(doc)
        except ValueError as exc:
            raise ExternalImportError(f'Ekstern kilde {relative}: {exc}') from exc
        if summary is not None:
            return summary
    from noark5_workflow.analysis.canonical_external_v0115_a5 import inspect_external_doc
    siegfried = inspect_external_doc(doc)
    if siegfried.get('format') == 'siegfried_json':
        return {'source_format': 'siegfried_json', **{k: v for k, v in siegfried.items() if k != 'format'}}
    return _pronom_statistics(doc, relative) or _arkade_entries(doc, relative)


def analyze_external_results(work: str | Path, selected_files: tuple[str | Path, ...],
                             *, write: bool = True, generated_at: str | None = None) -> dict:
    """Analyze *only* operator-selected Work files; writes isolated result projection."""
    from noark5_workflow.analysis.canonical_results import _validate_work
    root, identity = _validate_work(Path(work))
    if not selected_files or len(selected_files) > MAX_FILES:
        raise ExternalImportError('Velg 1-100 eksterne resultatfiler')
    canonical, _ = _canonical_reference(root, identity)
    sources = []
    seen = set()
    total_records = 0
    for source in selected_files:
        path, relative = _inside(root, source)
        if relative.casefold() in seen:
            raise ExternalImportError('Samme fil er valgt flere ganger')
        seen.add(relative.casefold())
        source_size = path.stat().st_size
        source_hash = _sha(path)
        try:
            result = inspect_selected_external(path, relative)
        except ExternalImportError as exc:
            raise ExternalImportError(f'Kan ikke analysere {relative}: {exc}') from exc
        if path.stat().st_size != source_size or _sha(path) != source_hash:
            raise ExternalImportError(f'Ekstern kilde {relative} ble endret under analysen; velg kilden på nytt')
        total_records += result.get('record_count', 0)
        if total_records > MAX_TOTAL_ITEMS:
            raise ExternalImportError(f'Ekstern kilde {relative}: samlet antall testposter '
                                      f'{total_records} overstiger {MAX_TOTAL_ITEMS}')
        sources.append({'evidence': {'work_relative_path': relative, 'sha256': source_hash,
                                      'bytes': source_size},
                        'analysis': result, 'authoritative_internal_master': False})
    document = {
        'model_id': MODEL, 'schema_version': '1.0',
        'generated_at': generated_at or datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'extraction_stable_id': identity['job_uid'],
        'canonical_reference': canonical,
        'sources': sources,
        'summary': {'selected_files': len(sources),
                    'reported_external_test_records': total_records,
                    'format_identification_files': sum(s['analysis']['interpretation'] == 'format_identification_only' for s in sources),
                    'unparsed_files': sum(s['analysis']['interpretation'] == 'not_parsed' for s in sources),
                    'technical_validation_verified': False, 'archive_creator_acceptance': None,
                    'depot_approval': None},
        'limitations': ['Arkade-teststatus gjengis uten mapping til godkjent/feilet',
                        'Arkade native XML og PRONOM CSV er ikke parset; normalisert PRONOM JSON kan tolkes',
                        'Siegfried identifiserer format, ikke integritet eller Noark-samsvar',
                        'Kildeutvalg er eksplisitt og ikke automatisk',
                        'Eksterne funn er ikke promotert til kanoniske mastertester'],
    }
    encoded = (json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    if len(encoded) > MAX_ANALYSIS_OUTPUT:
        selected = ', '.join(item['evidence']['work_relative_path'] for item in sources[:3])
        if len(sources) > 3:
            selected += f' (+{len(sources) - 3} andre)'
        raise ExternalImportError(f'Generert ekstern analyse er {len(encoded)} bytes; '
                                  f'grensen er {MAX_ANALYSIS_OUTPUT} bytes. '
                                  f'Valgte kilder: {selected}. Reduser utvalget av komplette kilder.')
    if write:
        folder = root / 'noark5_evidence'
        if not folder.is_dir() or folder.is_symlink():
            raise ExternalImportError('Kanonisk evidensmappe mangler eller er lenke')
        target = folder / 'canonical-external-analysis.json'
        if target.is_symlink():
            raise ExternalImportError('Resultatfil er en symbolsk lenke')
        fd, temporary = tempfile.mkstemp(prefix='.external-analysis-', suffix='.tmp', dir=folder)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return document


def discover_analysis_candidates(work: str | Path, *, limit: int = 150) -> list[dict[str, Any]]:
    """Find known external JSON outputs in this Work only; never auto-import.

    Search only known result roots, bound depth/count, reject symlinks and
    unknown filenames. Duplicate archival copies stay visible but unselected.
    """
    from noark5_workflow.analysis.canonical_results import _validate_work
    root, _ = _validate_work(Path(work))
    names = {
        'arkade5_results.json': 'Arkade 5 - Noark 5',
        'pronom_statistics.json': 'Arkade 5 - PRONOM',
    }
    found = []
    for folder_name in ('external_evidence', 'external_runs', 'arkade5_v2.13.1'):
        top = root / folder_name
        if not top.is_dir() or top.is_symlink():
            continue
        for folder, directories, filenames in os.walk(top, followlinks=False):
            current = Path(folder)
            depth = len(current.relative_to(top).parts)
            directories[:] = sorted(n for n in directories if depth < 6 and not (current / n).is_symlink())
            for name in sorted(filenames):
                candidate = current / name
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                label = names.get(name.lower())
                if label is None and name.lower().endswith('.json') and folder_name == 'external_evidence' and 'siegfried' in candidate.parts:
                    # Native Siegfried candidates: final interpretation is still validated.
                    label = 'Siegfried - JSON (kontroller format)'
                if label is None:
                    continue
                path, rel = _inside(root, candidate)
                found.append({'path': rel, 'label': label, 'bytes': path.stat().st_size, 'selected': False})
                if len(found) >= limit:
                    return found
    return found


def previous_analysis_selection(work: str | Path, candidates: list[dict[str, Any]]) -> list[str]:
    """Recall only previous selections that still exist under the chosen Work."""
    root = Path(work).resolve()
    result_path = root / OUT
    if not result_path.is_file() or result_path.is_symlink() or result_path.stat().st_size > MAX_ANALYSIS_OUTPUT:
        return []
    try:
        data = _json(result_path)
    except ExternalImportError:
        return []
    if data.get('model_id') != MODEL or not isinstance(data.get('sources'), list):
        return []
    allowed = {c['path'] for c in candidates}
    return [s['evidence']['work_relative_path'] for s in data['sources']
            if isinstance(s, dict) and isinstance(s.get('evidence'), dict)
            and s['evidence'].get('work_relative_path') in allowed]


def _canonical_reference(root: Path, identity: dict) -> tuple[dict, dict]:
    path = root / 'noark5_evidence' / 'canonical-results.json'
    if not path.is_file() or path.is_symlink():
        raise ExternalImportError('Kanonisk resultatindeks mangler')
    size = path.stat().st_size
    if size > MAX_CANONICAL_REFERENCE:
        raise ExternalImportError(f'Kanonisk resultatindeks noark5_evidence/canonical-results.json '
                                  f'er {size} bytes; grensen er {MAX_CANONICAL_REFERENCE} bytes')
    doc = _json(path)
    if doc.get('model_id') != 'noark5.canonical-results.v1' or doc.get('extraction', {}).get('stable_id') != identity['job_uid']:
        raise ExternalImportError('Kanonisk resultatindeks tilhoerer ikke valgt Work')
    return {'work_relative_path': 'noark5_evidence/canonical-results.json', 'sha256': _sha(path)}, doc
