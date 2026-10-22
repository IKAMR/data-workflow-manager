"""Read-only Noark 5 content profile from previously saved normal XPath results.

No new XML traversal, no U1/U2 regression, no imports and no changes to jobs.
The authoritative source is the normal result set referenced by the selected
job's depot report; known job-local output roots are a controlled fallback.
Never join archive parts by row position or by a possibly reused title.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_ROLE = 'dwm_xpath_normal_saved_result'

# (source test, metric, label, in Medium, per archive part)
DISTRIBUTIONS = {
    'folder_type': ('kdrs.c08', 'folder_type_counts', 'Mapper/saker – type', True, True),
    'folder_status': ('kdrs.c13', 'status_counts', 'Saker – saksstatus', False, True),
    'registration_type': ('kdrs.c14', 'type_counts', 'Registreringer – type', True, True),
    'journalpost_type': ('kdrs.c15', 'journalpost_type_counts', 'Journalposter – type', True, True),
    'journalpost_status': ('kdrs.c15', 'journal_status_counts', 'Journalposter – status', False, True),
    'document_type': ('kdrs.c21', 'document_type_counts', 'Dokumentbeskrivelser – dokumenttype', False, True),
    'document_relation': ('kdrs.c21', 'relation_type_counts', 'Dokumentbeskrivelser – tilknytning', False, True),
    'document_status': ('kdrs.c23', 'status_counts', 'Dokumentbeskrivelser – status', True, True),
    'variant_format': ('kdrs.c24', 'variant_format_counts', 'Dokumentobjekter – variantformat', True, True),
    'document_format': ('kdrs.c24', 'format_counts', 'Dokumentobjekter – registrert format (ikke PRONOM)', False, True),
    'correspondence_type': ('kdrs.f05', 'correspondence_party_type_counts', 'Korrespondanseparter – type', False, True),
    'writeoff_method': ('kdrs.f06', 'method_counts', 'Avskrivningsmåte', False, True),
    'document_flow': ('kdrs.f07', 'value_counts', 'Dokumentflyt', False, False),
    'access_restriction': ('kdrs.f08', 'access_restriction_counts', 'Skjerming – tilgangsrestriksjon', False, True),
    'disposal_decision': ('kdrs.f10', 'disposal_decision_value_counts', 'Kassasjonsvedtak – verdi', False, True),
    'deletion_type': ('kdrs.f13', 'deletion_type_counts', 'Slettinger – type', False, True),
}

# Additional counts, never confused with total numbers of cases or journalposts.
SCALARS = {
    'main_document_links': ('kdrs.c15', 'main_document_count', 'Dokumentbeskrivelser tilknyttet som hoveddokument', True, True),
    'other_document_links': ('kdrs.c15', 'non_main_document_count', 'Andre dokumentbeskrivelse-tilknytninger', False, True),
    'part_legacy': ('kdrs.f01', 'sakspart_count_v31_v40', 'Sakspart (Noark 3.1/4)', False, True),
    'part_noark5': ('kdrs.f01', 'part_count_v50', 'Part (Noark 5)', False, True),
    'notes': ('kdrs.f02', 'note_count', 'Merknader', True, False),
    'cross_references': ('kdrs.f03', 'cross_reference_children', 'Kryssreferanse-elementer', False, False),
    'precedents': ('kdrs.f04', 'precedent_count', 'Presedenser', False, False),
    'correspondence_parties': ('kdrs.f05', 'correspondence_party_count', 'Korrespondanseparter', False, True),
    'writeoffs': ('kdrs.f06', 'writeoff_method_count', 'Avskrivningsmåter registrert', False, True),
    'document_flows': ('kdrs.f07', 'document_flow_count', 'Dokumentflyter', False, False),
    'screenings': ('kdrs.f08', 'screening_count', 'Skjerminger', True, True),
    'disposal_decisions': ('kdrs.f10', 'disposal_decision_count', 'Kassasjonsvedtak', False, True),
    'performed_disposals': ('kdrs.f11', 'performed_disposal_count', 'Utførte kassasjoner', False, True),
    'conversions': ('kdrs.f12', 'conversion_count', 'Dokumentkonverteringer', False, True),
    'deletions': ('kdrs.f13', 'deletion_count', 'Slettinger utenom kassasjon', False, True),
}

TEST_IDS = frozenset(t[0] for t in (*DISTRIBUTIONS.values(), *SCALARS.values()))
MAX_JSON_BYTES = 64 * 1024 * 1024


def _read_json(path: Path) -> dict:
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError('Resultatfil over sikker lesegrense')
    result = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(result, dict):
        raise ValueError('Forventet et JSON-objekt')
    return result


def _normal_count(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _distribution(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    result = {}
    for label, count in value.items():
        n = _normal_count(count)
        if n is None:
            return None
        result[str(label)] = n
    return dict(sorted(result.items(), key=lambda item: (-item[1], item[0])))


def _roots(job) -> list[Path]:
    result = []
    for attr in ('_effective_work_operations', 'work_operations'):
        value = getattr(job, attr, None)
        if not value:
            continue
        base = Path(value)
        bases = [base]
        # DWM's internal root may be supplied already, including a01/a02.
        if base.name.lower() != 'dwm' and base.parent.name.lower() != 'dwm':
            bases.append(base / 'dwm')
        for candidate in bases:
            if candidate not in result:
                result.append(candidate)
    return result


def _belongs_to_job(run: Path, job, *, require_manifest=False) -> bool:
    manifest = run / 'artifact_manifest.json'
    if manifest.is_file():
        try:
            meta = _read_json(manifest)
        except (OSError, ValueError, json.JSONDecodeError):
            return False
        if meta.get('job_id') and str(meta['job_id']) != str(job.job_id):
            return False
    elif require_manifest:
        return False
    # JOB-nnn is reused between joblists. An unmanifested legacy folder
    # must at least have the correct local job prefix.
    return run.name.startswith(str(job.job_id) + '__')


def _normal_run(run: Path) -> bool:
    try:
        idx = _read_json(run / 'index.json')
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return idx.get('execution_profile') == 'normal' and isinstance(idx.get('tests'), list)


def find_normal_xpath_run(job, depot_report: dict) -> tuple[Path | None, str]:
    """Locate a job's saved run; never recurse into SIP/DOKUMENT/content.

    The full source path may be stale after a disk move. In that case reuse
    only its terminal RUN name underneath this job's configured work roots.
    """
    roots = _roots(job)
    if not roots:
        return None, 'Ingen lagret arbeidsmappe for denne jobben.'
    ref = str(((depot_report or {}).get('evidence') or {}).get('source_xpath_run') or '').strip()
    basename = ref.replace('\\', '/').rstrip('/').split('/')[-1] if ref else ''
    for root in roots:
        source = root / 'noark5_tests' / 'xpath'
        if basename and basename not in ('.', '..'):
            run = source / basename
            if run.is_dir() and _belongs_to_job(run, job) and _normal_run(run):
                return run, ''
    # No anchor: try a bounded, direct-child discovery of documented runs.
    # When a report explicitly named a run, do not substitute another one.
    if ref:
        return None, 'Lagret XPath-kjøring finnes ikke lenger på jobbens arbeidsområde: ' + basename
    candidates = []
    for root in roots:
        source = root / 'noark5_tests' / 'xpath'
        if not source.is_dir():
            continue
        try:
            for run in source.iterdir():
                if run.is_dir() and _belongs_to_job(run, job) and _normal_run(run):
                    candidates.append(run)
        except OSError:
            continue
    if not candidates:
        return None, 'Ingen lagret normal DWM XPath-kjøring funnet for jobben.'
    # The normal run folders have sortable RUN timestamps; never combine runs.
    return max(candidates, key=lambda run: run.name), ''


def _indexed_result(run: Path, index: dict, test_id: str) -> tuple[dict | None, str]:
    tests = [row for row in index.get('tests') or []
             if isinstance(row, dict) and row.get('test_id') == test_id]
    if len(tests) != 1:
        return None, 'mangler eller duplisert testoppføring'
    row = tests[0]
    if row.get('status') != 'ok':
        return None, str(row.get('status') or 'ikke fullført')
    # Read only the exact known test file in the known results directory.
    expected = test_id.replace('.', '_') + '.json'
    raw_path = str(row.get('file') or '').replace('\\', '/')
    if raw_path != 'results/' + expected:
        return None, 'uvanlig resultatsti – ikke lest'
    try:
        document = _read_json(run / 'results' / expected)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, 'resultatfil kunne ikke leses: ' + str(exc)
    if document.get('test_id') != test_id or document.get('status') != 'ok':
        return None, 'test-ID eller status stemmer ikke'
    values = document.get('values')
    if not isinstance(values, dict):
        return None, 'resultatverdier mangler'
    return values, ''


def _parts(values: dict, *, test_id: str) -> tuple[dict, list[str]]:
    rows = values.get('_archive_parts') or values.get('archive_parts') or []
    parts = {}
    ambiguous = set()
    warnings = []
    if not isinstance(rows, list):
        return {}, [test_id + ': ugyldig arkivdelliste']
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        sid = str((entry.get('archive_part') or {}).get('system_id') or '').strip()
        if not sid:
            continue
        if sid in ambiguous:
            continue
        if sid in parts:
            parts.pop(sid, None)
            ambiguous.add(sid)
            warnings.append(test_id + ': duplisert system-ID: ' + sid)
            continue
        part_values = entry.get('values')
        if isinstance(part_values, dict):
            parts[sid] = part_values
    return parts, warnings


def _fact_meta(test_id: str, metric: str, label: str, *, values: Any, is_distribution: bool, medium: bool):
    return {'label': label, 'test_id': test_id, 'metric_id': metric,
            'data_role': DATA_ROLE, 'medium': medium, 'value': values,
            'value_type': 'distribution' if is_distribution else 'count'}


def build_job_content_profile(job, depot_report: dict | None) -> dict:
    """Read existing single-test facts for one job; no XPath execution."""
    run, reason = find_normal_xpath_run(job, depot_report or {})
    result = {'data_role': DATA_ROLE, 'status': 'not_available',
              'source_run': str(run) if run else None, 'distributions': {},
              'scalars': {}, 'archive_parts': {}, 'tests_read': [],
              'diagnostic': reason, 'warnings': []}
    if run is None:
        return result
    try:
        index = _read_json(run / 'index.json')
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result['diagnostic'] = 'Kunne ikke lese XPath-indeks: ' + str(exc)
        return result
    loaded = {}
    part_loaded = {}
    for test_id in sorted(TEST_IDS):
        values, diagnostic = _indexed_result(run, index, test_id)
        if values is not None:
            loaded[test_id] = values
            part_loaded[test_id], warnings = _parts(values, test_id=test_id)
            result['tests_read'].append(test_id)
            result['warnings'].extend(warnings)
        elif diagnostic.startswith('uvanlig') or diagnostic.startswith('resultatfil') or diagnostic.startswith('test-ID'):
            result['warnings'].append(test_id + ': ' + diagnostic)
    for key, (test_id, metric, label, medium, allow_part) in DISTRIBUTIONS.items():
        if test_id not in loaded:
            continue
        values = _distribution(loaded[test_id].get(metric))
        if values is not None:
            result['distributions'][key] = _fact_meta(test_id,metric,label,
                values=values,is_distribution=True,medium=medium)
        if allow_part:
            for sid, part_values in part_loaded.get(test_id,{}).items():
                breakdown = _distribution(part_values.get(metric))
                if breakdown is not None:
                    dest = result['archive_parts'].setdefault(sid, {'distributions': {}, 'scalars': {}})
                    dest['distributions'][key] = _fact_meta(test_id,metric,label,
                        values=breakdown,is_distribution=True,medium=medium)
    for key, (test_id, metric, label, medium, allow_part) in SCALARS.items():
        if test_id not in loaded:
            continue
        value = _normal_count(loaded[test_id].get(metric))
        if value is not None:
            result['scalars'][key] = _fact_meta(test_id,metric,label,
                values=value,is_distribution=False,medium=medium)
        if allow_part:
            for sid, part_values in part_loaded.get(test_id,{}).items():
                count = _normal_count(part_values.get(metric))
                if count is not None:
                    dest = result['archive_parts'].setdefault(sid, {'distributions': {}, 'scalars': {}})
                    dest['scalars'][key] = _fact_meta(test_id,metric,label,
                        values=count,is_distribution=False,medium=medium)
    # Explicit legacy per-part fallback, never used to override c15.
    fallback, diagnostic = _indexed_result(run, index, 'kdrs.c15_01')
    if fallback is not None:
        extra, warnings = _parts(fallback, test_id='kdrs.c15_01')
        result['warnings'].extend(warnings)
        for sid, values in extra.items():
            dest = result['archive_parts'].setdefault(sid, {'distributions': {}, 'scalars': {}})
            if 'journalpost_type' not in dest['distributions']:
                observed = _distribution(values.get('journalpost_type_counts'))
                if observed is not None:
                    dest['distributions']['journalpost_type'] = _fact_meta(
                        'kdrs.c15_01','journalpost_type_counts','Journalposter – type',
                        values=observed,is_distribution=True,medium=True)
    if result['distributions'] or result['scalars'] or result['archive_parts']:
        result['status'] = 'available'
        result['diagnostic'] = ''
    else:
        result['diagnostic'] = 'Normal XPath-kjøring finnes, men ingen relevante type-/statusverdier er tilgjengelige.'
    return result


def attach_content_profiles(snapshot: dict, jobs, package: dict) -> dict:
    """Extend a20's canonical snapshot without mutating source reports."""
    source_records = package.get('jobs') or []
    if len(source_records) != len(jobs) or len(snapshot.get('jobs') or []) != len(jobs):
        raise ValueError('Kan ikke knytte innholdsprofiler: jobbantall er forskjellig')
    for job, source, target in zip(jobs, source_records, snapshot['jobs']):
        if str(getattr(job,'job_id','')) != str(source.get('job_id')) or target['job_id'] != str(source.get('job_id')):
            raise ValueError('Kan ikke knytte innholdsprofil til feil jobb-ID')
        profile = build_job_content_profile(job, source.get('depot_report'))
        # No type inference when DWM master is unavailable; imported external
        # KDRS/Arkade evidence remains separate in the original report model.
        target['content_profile'] = profile
        native_ids = {str(p['system_id']) for p in target['archive_parts'] if p.get('system_id')}
        unmatched = set(profile['archive_parts']) - native_ids
        if unmatched and target.get('has_depot_report'):
            profile['warnings'].append(str(len(unmatched))+
                ' arkivdel-ID-er i XPath-profilen finnes ikke i depotrapportens native arkivdeler.')
    return snapshot
