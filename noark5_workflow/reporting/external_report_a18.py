"""Read-only Arkade 5, PRONOM and KDRS Query evidence for selected-job reports.

This adapter reuses the external result bank and persisted depot evidence.  It
never imports/runs tests, changes source results, or treats external findings as
DWM master values.  One selected job and N selected jobs use the same adapter.
"""
from __future__ import annotations

from html import escape
import hashlib
import json
from pathlib import Path
from typing import Any


def _h(value: Any) -> str:
    return escape('–' if value is None else str(value), quote=True)


def _table(columns, rows) -> str:
    heading = ''.join('<th>' + _h(v) + '</th>' for v in columns)
    body = ''.join('<tr>' + ''.join('<td>' + _h(v) + '</td>' for v in row) + '</tr>' for row in rows)
    return '<table><thead><tr>' + heading + '</tr></thead><tbody>' + body + '</tbody></table>'


def _work_source(job) -> Path | None:
    """Use only this job's documented work roots, never scan sibling jobs."""
    candidates = []
    for attr in ('_effective_work_operations', 'work_operations'):
        value = getattr(job, attr, None)
        if value:
            base = Path(value)
            candidates.extend((base, base / 'dwm'))
    for base in dict.fromkeys(candidates):
        if (base / 'external_evidence' / 'kdrs_query').is_dir() or (base / 'external_evidence' / 'arkade5').is_dir():
            return base
    return None


def collect_job_evidence(job, depot_report: dict | None) -> dict[str, Any]:
    """Materialize stored external evidence for a SINGLE job, without writes.

    Arkade/PRONOM fall back to the pinned depot report when the external work
    folder is unavailable.  KDRS Query is never inferred from DWM XPath output.
    """
    data = depot_report or {}
    arkade = ((data.get('external_validation') or {}).get('arkade5') or {})
    imports = {}
    for item in arkade.get('imports') or []:
        if isinstance(item, dict) and item.get('import_id'):
            imports[str(item['import_id'])] = {
                'import_id': item['import_id'],
                'source_version': item.get('source_version'),
                'source_file': item.get('source_file'),
                'source_sha256': item.get('source_sha256'),
                'date_of_testing': item.get('date_of_testing'),
                'number_of_tests_run': item.get('number_of_tests_run'),
                'number_of_errors': item.get('number_of_errors'),
                'number_of_warnings': item.get('number_of_warnings'),
                'pronom': item.get('pronom') or {},
                'control_areas': (item.get('coverage') or {}).get('arkade_control_areas') or [],
                'tests': [],
            }

    result = {
        'schema': 'ikamr.noark5.external_report.a18.v1',
        'job_id': str(getattr(job, 'job_id', '')),
        'source_role': 'external_evidence_only',
        'arkade5': {'imports': list(imports.values()), 'summary': arkade.get('summary') or {},
                    'pronom_summary': arkade.get('pronom_summary') or {}},
        'kdrs_query': {'resources': [], 'summary': {}},
        'diagnostics': [],
    }
    work = _work_source(job)
    if work is None:
        result['diagnostics'].append('Ingen tilgjengelig importmappe for denne jobben; Arkade/PRONOM vises kun fra lagret depotrapport, KDRS Query er ukjent.')
        return result

    try:
        from noark5_workflow.external_evidence.result_bank import build_external_result_bank
        from noark5_workflow.external_evidence.kdrs_query_views import build_kdrs_query_report_data
        bank = build_external_result_bank(work)
        for group in bank.get('groups') or []:
            source_system = group.get('source_system')
            import_id = str(group.get('source_import_id') or '')
            if source_system == 'Arkade 5' and import_id:
                entry = imports.setdefault(import_id, {
                    'import_id': import_id, 'source_version': group.get('source_version'),
                    'source_file': group.get('source_file'), 'source_sha256': group.get('source_sha256'),
                    'date_of_testing': group.get('source_test_date'),
                    'number_of_tests_run': group.get('source_number_of_tests'),
                    'number_of_errors': group.get('source_number_of_errors'),
                    'number_of_warnings': group.get('source_number_of_warnings'),
                    'pronom': {}, 'control_areas': [], 'tests': [],
                })
                entry['tests'] = list(group.get('resources') or [])
        # New PRONOM statistics can have arrived after the native depot snapshot.
        # Use the existing import readers, without changing any persisted report.
        try:
            from noark5_workflow.external_evidence.arkade5 import list_arkade5_imports
            from noark5_workflow.external_evidence.arkade5_pronom import (
                load_arkade5_pronom_statistics, summarize_arkade5_pronom_statistics,
            )
            for manifest in list_arkade5_imports(work):
                import_id = str(manifest.get('import_id') or '')
                if import_id not in imports:
                    continue
                normalized = load_arkade5_pronom_statistics(work, manifest)
                if normalized:
                    latest = summarize_arkade5_pronom_statistics(normalized, manifest=manifest)
                    if latest.get('available'):
                        imports[import_id]['pronom'] = latest
        except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
            result['diagnostics'].append('PRONOM-oppdatering kunne ikke leses: ' + str(exc))
        result['arkade5']['imports'] = list(imports.values())
        result['kdrs_query'] = build_kdrs_query_report_data(bank)
        # A report selection is only shown when its source observation still
        # exists and has the identical source SHA-256 (see kdrs_query_selection).
        try:
            from noark5_workflow.external_evidence.kdrs_query_selection import load_choices, candidates
            valid = {r['observation_id']: r for r in candidates(work)}
            chosen = {}
            selected_ids = set()
            for metric, item in load_choices(work).items():
                if not isinstance(item, dict):
                    continue
                found = valid.get(item.get('observation_id'))
                if (found is not None and found.get('source_sha256') == item.get('source_sha256')
                        and found.get('metric_id') == item.get('metric_id')):
                    chosen[metric] = dict(item)
                    resource_id = str(item.get('observation_id')).split(':exact:', 1)[0]
                    if resource_id:
                        selected_ids.add(resource_id)
            result['kdrs_query']['selected_report_values'] = chosen
            for r in result['kdrs_query'].get('resources') or []:
                r['selected_for_report'] = r.get('resource_id') in selected_ids
        except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
            result['diagnostics'].append('KDRS-valgte verdier kunne ikke bekreftes: ' + str(exc))
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        result['diagnostics'].append('Kunne ikke lese importert ekstern evidens: ' + str(exc))

    # PRONOM is in the depot snapshot. Never report a missing import as zero files.
    for entry in result['arkade5']['imports']:
        if not (entry.get('pronom') or {}).get('available'):
            continue
        # Preserve the imported statistics and their original source identity.
        entry['pronom'] = dict(entry['pronom'])
    return result


def render_job_evidence(evidence: dict[str, Any], *, level: str = 'Medium') -> str:
    """Human-readable detail (machine-readable evidence keeps ALL observations)."""
    job_id = _h(evidence.get('job_id'))
    parts = [f'<h3>{job_id} – Arkade 5 / PRONOM / KDRS Query</h3>',
             '<p>Alle eksterne resultater er kildeangitt og holdes adskilt fra DWM-testene og depotets vurdering.</p>']
    for diagnostic in evidence.get('diagnostics') or []:
        parts.append('<p class="muted">' + _h(diagnostic) + '</p>')
    imports = (evidence.get('arkade5') or {}).get('imports') or []
    if not imports:
        parts.append('<p>Arkade 5: Ingen importert evidens dokumentert i dette rapportgrunnlaget.</p>')
    for item in imports:
        parts.append('<h4>Arkade 5 – import ' + _h(item.get('import_id')) + '</h4>')
        parts.append(_table(('Versjon', 'Testdato', 'Kildefil', 'SHA-256', 'Tester', 'Rapporterte feil'), [
            (item.get('source_version'), item.get('date_of_testing'), item.get('source_file'),
             item.get('source_sha256'), item.get('number_of_tests_run'), item.get('number_of_errors'))]))
        tests = item.get('tests') or []
        if tests:
            rows = [(r.get('test_id'), r.get('test_name'), r.get('status'), r.get('number_of_errors'),
                     r.get('coverage_classification'), r.get('relationship_to_internal')) for r in tests]
        else:
            rows = [(r.get('arkade_test_id'), r.get('arkade_test_name'),
                     (r.get('arkade') or {}).get('status'), (r.get('arkade') or {}).get('number_of_errors'),
                     r.get('relation'), r.get('combined_status')) for r in item.get('control_areas') or []]
        parts.append('<h4>Noark 5-tester</h4>')
        parts.append(_table(('Test', 'Navn', 'Status', 'Feil', 'Dekning', 'Avstemming'), rows)
                     if rows else '<p>Testdetaljer er ikke tilgjengelige i rapportgrunnlaget.</p>')
        pronom = item.get('pronom') or {}
        stats = pronom.get('statistics') or {}
        if pronom.get('available'):
            parts.append('<h4>Siegfried / PRONOM</h4>')
            parts.append(_table(('Måltall', 'Verdi'), [
                ('Filer i statistikkgrunnlaget', stats.get('total_files')),
                ('Uidentifiserte filer', stats.get('unidentified_files')),
                ('Formatidentifikatorer', stats.get('unique_format_ids')),
                ('Statistikkrader', stats.get('row_count')),
                ('Kildefil', (stats.get('source') or {}).get('original_name')),
                ('SHA-256', (stats.get('source') or {}).get('sha256')),
            ]))
            if stats.get('rows'):
                rows = stats['rows']
                limit = 80 if level == 'Full' else 20
                parts.append(_table(('Format-ID', 'Filtype', 'Formatversjon', 'RAF-220301', 'Antall'), [
                    (r.get('format_id'), r.get('file_type'), r.get('format_version'),
                     r.get('raf_220301'), r.get('count')) for r in rows[:limit] if isinstance(r, dict)
                ]))
                if len(rows) > limit:
                    parts.append('<p class="muted">Viser ' + str(limit) + ' av ' + str(len(rows)) +
                                 ' formatrader; samtlige er bevart i JSON-grunnlaget.</p>')
        else:
            parts.append('<p>PRONOM: Statistikken er ikke importert for denne Arkade-kjøringen (ukjent, ikke null).</p>')
        detailed = pronom.get('detailed_file_inventory') or {}
        if detailed.get('found') and not detailed.get('imported'):
            parts.append('<p>PRONOM-filoversikt finnes som kilde, men er ikke importert som dokumentnivåresultater.</p>')

    kdrs = evidence.get('kdrs_query') or {}
    resources = kdrs.get('resources') or []
    parts.append('<h4>KDRS Query – Standard / U1 / U2</h4>')
    if not resources:
        parts.append('<p>Ingen KDRS Query-resultater tilgjengelige for denne jobben. Dette betyr ikke at analysen hadde null funn.</p>')
    else:
        parts.append(_table(('Type','Test','Arkivdel','Observasjoner','Kilde'), [
            (r.get('report_type'), r.get('test_point') or r.get('test_id'),
             r.get('archive_part_title') or 'Gjelder hele uttrekket',
             len(r.get('observations') or []), r.get('source_file')) for r in resources]))
        max_rows = 20 if level == 'Full' else 5
        for r in resources:
            observations = r.get('observations') or []
            if not observations:
                continue
            shown = observations[:max_rows]
            parts.append('<h4>' + _h(r.get('test_point') or r.get('test_id')) + ' – ' +
                         _h(r.get('test_name')) + ' (' + _h(r.get('report_type')) + ')</h4>')
            parts.append(_table(('Linje', 'Resultat'), [(x.get('line'), x.get('text')) for x in shown]))
            if len(shown) < len(observations):
                parts.append('<p class="muted">Viser ' + str(len(shown)) + ' av ' + str(len(observations)) +
                             ' observasjoner. Samtlige finnes i tilhørende JSON-evidens.</p>')
    return ''.join(parts)


REPORT_METRICS = (
    ('archive_part_count', 'Arkivdeler'),
    ('folder_count', 'Mapper'),
    ('registration_count', 'Registreringer'),
    ('journalpost_count', 'Journalposter'),
    ('document_description_count', 'Dokumentbeskrivelser'),
    ('document_object_count', 'Dokumentobjekter'),
)


def verified_main_counts(depot_report: dict | None, report_path: str | Path | None):
    """Read the existing SHA-bound effective projection; never mutate native DWM.

    Raw imported KDRS numbers are NOT automatically promoted to main totals.
    Only an explicitly selected, scope-verified projection is effective.
    """
    summary = (depot_report or {}).get('summary') or {}
    values = {}
    for key, _label in REPORT_METRICS:
        raw = summary.get(key)
        dwm = raw if type(raw) is int and raw >= 0 else None
        values[key] = {'dwm_value': dwm, 'effective_value': dwm,
                       'source': 'DWM' if dwm is not None else None}
    if not report_path:
        return values, ''
    report_path = Path(report_path)
    candidate = report_path.with_name('depot-effective-evidence.json')
    if not candidate.is_file():
        return values, ''
    try:
        original = report_path.read_bytes()
        projection = json.loads(candidate.read_text(encoding='utf-8'))
        if projection.get('native_report_sha256') != hashlib.sha256(original).hexdigest():
            return values, 'Valgte KDRS-verdier er ikke innarbeidet: depotrapportens SHA-256 samsvarer ikke.'
        if projection.get('kind') != 'noark5_effective_evidence_projection':
            return values, 'Ukjent struktur i avstemt KDRS-evidens.'
        companion_name = projection.get('evidence_companion_file')
        companion_sha = projection.get('evidence_companion_sha256')
        if companion_name or companion_sha:
            if (not isinstance(companion_name, str) or not companion_name
                    or Path(companion_name).name != companion_name
                    or not isinstance(companion_sha, str)):
                return values, 'Ugyldig kildehenvisning i avstemt KDRS-evidens.'
            companion_path = candidate.with_name(companion_name)
            if (not companion_path.is_file() or
                    hashlib.sha256(companion_path.read_bytes()).hexdigest() != companion_sha):
                return values, 'KDRS-evidensen er endret eller mangler; ingen ekstern verdi brukes.'
        for key, _label in REPORT_METRICS:
            source = (projection.get('whole') or {}).get(key) or {}
            dwm = values[key]['dwm_value']
            new = source.get('effective_value')
            if (source.get('status') == 'external_evidence_selected'
                    and source.get('effective_source') == 'KDRS Query'
                    and source.get('dwm_value') == dwm
                    and isinstance(source.get('evidence'), dict)
                    and type(new) is int and new >= 0):
                values[key]['effective_value'] = new
                values[key]['source'] = 'KDRS Query'
    except (OSError, ValueError, TypeError) as exc:
        return values, 'Avstemt KDRS-evidens kunne ikke leses: ' + str(exc)
    return values, ''


def report_count_overview(rows):
    """Shared main/one-job count overview, with explicit data coverage.

    rows: (job, native_report, report_path, diagnostic) tuples.
    Each selected job contributes at most once. Unknown is never zero.
    """
    job_rows = []
    for job, data, path, diagnostic in rows:
        values, warning = verified_main_counts(data, path)
        # Explicit KDRS Query report choices are scope-checked and source-hash
        # checked by collect_job_evidence / kdrs_query_selection.candidates.
        # A missing DWM number can be reported from that chosen source, even
        # when the native XPath/depot analysis could not produce a number.
        # Conflicting DWM/KDRS numbers remain visible side-by-side.
        evidence = collect_job_evidence(job, data)
        selected = (evidence.get('kdrs_query') or {}).get('selected_report_values') or {}
        for key, item in selected.items():
            if key not in values or not isinstance(item, dict):
                continue
            number = item.get('value')
            if type(number) is not int or number < 0:
                continue
            values[key]['kdrs_selected_value'] = number
            if (values[key]['dwm_value'] is None
                    and values[key]['effective_value'] is None):
                values[key]['effective_value'] = number
                values[key]['source'] = 'KDRS Query (valgt)'
        job_rows.append({'job_id': str(job.job_id), 'values': values, 'warning': warning,
                         'diagnostic': diagnostic})
    aggregate = []
    total_jobs = len(job_rows)
    for key, label in REPORT_METRICS:
        count_dwm = 0
        count_effective = 0
        sum_dwm = 0
        sum_effective = 0
        kdrs_jobs = 0
        for job in job_rows:
            row = job['values'][key]
            native = row['dwm_value']
            effective = row['effective_value']
            if native is not None:
                sum_dwm += native
                count_dwm += 1
            if effective is not None:
                sum_effective += effective
                count_effective += 1
            if str(row['source'] or '').startswith('KDRS Query'):
                kdrs_jobs += 1
        aggregate.append({'metric': key, 'label': label, 'dwm_sum': sum_dwm,
                          'dwm_coverage': count_dwm, 'effective_sum': sum_effective,
                          'effective_coverage': count_effective, 'total_jobs': total_jobs,
                          'kdrs_jobs': kdrs_jobs})
    return {'jobs': job_rows, 'totals': aggregate}


def render_count_overview(overview):
    """Present DWM and accepted KDRS values distinctly, not as two additive totals."""
    total_rows = []
    for row in overview['totals']:
        n = row['total_jobs']
        total_rows.append((row['label'],
            f"{row['dwm_sum']:,} ({row['dwm_coverage']}/{n} uttrekk)".replace(',', ' ')
                if row['dwm_coverage'] else 'Ukjent',
            f"{row['effective_sum']:,} ({row['effective_coverage']}/{n} uttrekk)".replace(',', ' ')
                if row['effective_coverage'] else 'Ukjent',
            row['kdrs_jobs']))
    parts = ['<p>Opptelling er kildeavstemt per uttrekk. En eksplisitt valgt og kontrollert KDRS Query-verdi kan brukes når DWM mangler tallet;'
             ' motstridende DWM-verdier beholdes inntil avstemming er bekreftet. Verdiene legges aldri sammen. Delvise summer er merket med dekning.</p>',
             _table(('Måltall','DWM-sum (dekning)','Rapportverdi (dekning)','Uttrekk med valgt KDRS'), total_rows)]
    chosen = [(r['job_id'], key, v['dwm_value'],
               v.get('kdrs_selected_value', v['effective_value']),
               v['source'] or 'DWM (alternativ vist separat)')
              for r in overview['jobs'] for key, v in r['values'].items()
              if 'kdrs_selected_value' in v or str(v['source'] or '').startswith('KDRS Query')]
    if chosen:
        parts.append('<h3>Eksplisitt valgte KDRS Query-verdier</h3>')
        parts.append('<p>Når DWM-verdien finnes og KDRS-verdien avviker, vises'
                     ' de separat til avstemmingen er bekreftet.</p>')
        parts.append(_table(('Jobb','Måltall','DWM','Valgt KDRS','Rapportkilde'),chosen))
    for job in overview['jobs']:
        if job['warning']:
            parts.append('<p class="note">' + _h(job['job_id'] + ': ' + job['warning']) + '</p>')
    return ''.join(parts)


def external_status_rows(rows):
    """Source coverage for each selected job, even if it lacks a native report."""
    status = []
    for job, data, _path, diagnostic in rows:
        evidence = collect_job_evidence(job, data)
        imports = (evidence.get('arkade5') or {}).get('imports') or []
        kdrs = evidence.get('kdrs_query') or {}
        resources = kdrs.get('resources') or []
        pronom = [entry.get('pronom') or {} for entry in imports]
        pronom_count = sum(bool(item.get('available')) for item in pronom)
        pronom_files = sum(int((item.get('statistics') or {}).get('total_files') or 0)
                           for item in pronom if item.get('available'))
        pronom_unknown = not bool(pronom_count)
        types = {str(r.get('report_type') or '').lower() for r in resources}
        arkade_tests = sum(len(entry.get('tests') or entry.get('control_areas') or []) for entry in imports)
        versions = ', '.join(sorted({str(entry.get('source_version')) for entry in imports
                                     if entry.get('source_version')})) or None
        latest_date = max((str(entry.get('date_of_testing')) for entry in imports
                           if entry.get('date_of_testing')), default=None)
        selected = kdrs.get('selected_report_values') or {}
        status.append({'job_id': str(job.job_id), 'depot_report': data is not None,
                       'arkade_imports': len(imports), 'arkade_tests': arkade_tests,
                       'arkade_versions': versions, 'arkade_latest_test_date': latest_date,
                       'pronom_sets': pronom_count if imports else None,
                       'pronom_files': None if pronom_unknown else pronom_files,
                       'kdrs_standard': sum(str(r.get('report_type') or '').lower() == 'standard' for r in resources),
                       'kdrs_u1': sum(str(r.get('report_type') or '').lower() in ('u01','u1') for r in resources),
                       'kdrs_u2': sum(str(r.get('report_type') or '').lower() in ('u02','u2') for r in resources),
                       'kdrs_selected': len(selected),
                       'source_accessible': bool(_work_source(job)),
                       'diagnostic': diagnostic,
                       'warnings': evidence.get('diagnostics') or []})
    return status


def render_external_status(rows):
    out = []
    for r in rows:
        if not r['source_accessible'] and r['arkade_imports'] == 0:
            arkade = 'Ukjent (kilde utilgjengelig)'
        else:
            arkade = r['arkade_imports']
        if not r['source_accessible']:
            kdrs = 'Ukjent'
        else:
            kdrs = 'Standard: %s, U1: %s, U2: %s' % (
                r['kdrs_standard'], r['kdrs_u1'], r['kdrs_u2'])
        pronom = 'Ukjent' if r['pronom_files'] is None else str(r['pronom_files'])
        description = (str(arkade) + (' · ' + r['arkade_versions'] if r['arkade_versions'] else '')
                       + (' · ' + r['arkade_latest_test_date'] if r['arkade_latest_test_date'] else ''))
        pronom_label = ('Ukjent' if r['pronom_files'] is None else
                        f"{r['pronom_sets']} sett / {pronom} filer")
        out.append((r['job_id'], 'Funnet' if r['depot_report'] else 'Mangler',
                    description, r['arkade_tests'] if r['arkade_imports'] else '–',
                    pronom_label, kdrs, r['kdrs_selected'] if r['source_accessible'] else '–'))
    return ('<p>Importstatus gjelder hver enkelt jobb. Arkade-testresultater, PRONOM-filstatistikk'
            ' og KDRS Query-ressurser er forskjellige måltall. PRONOM-tall per import er ikke antall unike filer.</p>'
            + _table(('Jobb','Depotrapport','Arkade-importer','Arkade-kontroller','PRONOM-filobservasjoner',
                      'KDRS Query (seksjoner)','Valgte KDRS-felt'), out))
