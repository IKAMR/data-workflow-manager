"""One read-only source comparison for single-job and selected-jobs Noark 5 reports.

DWM XPath, EACH Arkade 5 test run, PRONOM and KDRS Query are peers as evidence
but not automatically interchangeable values. Only semantically exact KDRS
observations can be compared; they do not replace DWM counts or review status.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from html import escape
import re
from typing import Any

from .external_report_a18 import collect_job_evidence, REPORT_METRICS
from .source_identity_a18 import source_identity_warnings

LABELS = dict(REPORT_METRICS)
LABELS.update((('case_folder_count', 'Saksmapper'), ('correspondence_party_count', 'Korrespondanseparter')))


def _h(v):
    return escape('–' if v is None else str(v), quote=True)


def _table(headings, rows):
    columns = ''.join('<th>' + _h(v) + '</th>' for v in headings)
    values = ''.join('<tr>' + ''.join('<td>' + _h(v) + '</td>' for v in row) + '</tr>' for row in rows)
    return '<table><thead><tr>' + columns + '</tr></thead><tbody>' + values + '</tbody></table>'


def _count(v):
    return v if type(v) is int and v >= 0 else None


def _key(value):
    return re.sub(r'\s+', ' ', str(value or '').strip()).casefold()


def _dwm_tests(data):
    tests = ((data or {}).get('technical_validation') or {}).get('tests') or []
    return [dict(test_id=r.get('test_id'), test_point=r.get('test_point'), status=r.get('status'),
                 legacy_job_id=r.get('legacy_job_id'), reconciliation=r.get('reconciliation_summary'))
            for r in tests if isinstance(r, dict)]


def _arkade_rows(evidence):
    runs = []
    for item in (evidence.get('arkade5') or {}).get('imports') or []:
        if not isinstance(item, dict):
            continue
        tests = []
        source = item.get('tests') or []
        if source:
            for t in source:
                if not isinstance(t, dict):
                    continue
                tests.append({'id': t.get('test_id'), 'name': t.get('test_name'),
                              'status': t.get('status'), 'errors': t.get('number_of_errors'),
                              'dwm_candidates': list(t.get('dwm_candidates') or []),
                              'coverage': t.get('coverage_classification'),
                              'relationship': t.get('relationship_to_internal'),
                              'source_file': t.get('source_file') or item.get('source_file'),
                              'source_sha256': t.get('source_sha256') or item.get('source_sha256'),
                              'results': list(t.get('results') or [])})
        else:
            # An older persisted depot report has coverage/status but no full test output.
            for t in item.get('control_areas') or []:
                if not isinstance(t, dict):
                    continue
                a = t.get('arkade') or {}
                tests.append({'id': t.get('arkade_test_id'), 'name': t.get('arkade_test_name'),
                              'status': a.get('status'), 'errors': a.get('number_of_errors'),
                              'dwm_candidates': list(t.get('dwm_test_ids') or []),
                              'coverage': t.get('relation'),
                              'relationship': t.get('combined_status'),
                              'source_file': item.get('source_file'),
                              'source_sha256': item.get('source_sha256'),
                              'results': []})
        runs.append({'import_id': item.get('import_id'), 'source_version': item.get('source_version'),
                     'source_file': item.get('source_file'), 'source_sha256': item.get('source_sha256'),
                     'test_date': item.get('date_of_testing'), 'test_count': item.get('number_of_tests_run'),
                     'error_count': item.get('number_of_errors'), 'warning_count': item.get('number_of_warnings'),
                     'tests': tests, 'pronom': item.get('pronom') or {}})
    return runs


def _match_part(title, parts):
    # Index from KDRS is NOT assumed to identify a DWM archive part.
    matches = [p for p in parts if _key(p['title']) and _key(p['title']) == _key(title)]
    return matches[0] if len(matches) == 1 else None


def _kdrs_exact_observations(resources, data):
    """Extract definition-backed KDRS numbers, retaining every source occurrence.

    No summing between Standard/U1 or between multiple KDRS imports. No
    inferred scope from historic filenames or numeric U2 part ordinals.
    """
    if not resources:
        return []
    from noark5_workflow.external_evidence.kdrs_query_semantics import extract_field_observations
    parts = []
    for idx, item in enumerate((data or {}).get('archive_parts') or [], 1):
        ident = (item or {}).get('archive_part') or {}
        parts.append({'index': idx, 'title': ident.get('title') or '',
                      'system_id': ident.get('system_id'), 'data': item})
    rows = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        typ = str(resource.get('report_type') or '').lower()
        test_id = str(resource.get('test_id') or '')
        match = re.fullmatch(r'kdrs\.([c-f]\d+(?:\.\d+)?)', test_id, re.I)
        legacy = match.group(1).replace('.', '_').upper() if match else ''
        if typ in ('u01','u1'):
            legacy = 'U01'
        elif typ in ('u02','u2'):
            legacy = 'U02'
        raw = str(resource.get('raw_text') or '')
        if not raw or not legacy:
            continue
        observed = extract_field_observations(raw, report_type=typ,
                                             legacy_job_id=legacy,
                                             archive_part_index=resource.get('archive_part_index'),
                                             archive_part_title=resource.get('archive_part_title'))
        for line in observed:
            for fact in line.get('facts') or []:
                if (fact.get('mapping_status') != 'exact' or fact.get('value_kind') != 'count'
                        or not fact.get('metric_id') or _count(fact.get('value')) is None):
                    continue
                title = line.get('archive_part_title') or resource.get('archive_part_title')
                matched = _match_part(title, parts) if title else None
                has_part = bool(title or line.get('archive_part_index') is not None or
                                resource.get('archive_part_index') is not None)
                scope = ('arkivdel' if matched else 'ikke_tilordnet' if has_part else 'uttrekk')
                dwm = ((matched['data'] if matched else {}).get(fact['metric_id']) if matched else
                       ((data or {}).get('summary') or {}).get(fact['metric_id']) if scope == 'uttrekk' else None)
                dwm = _count(dwm)
                value = _count(fact['value'])
                relation = ('ikke_tilordnet' if scope == 'ikke_tilordnet' else
                            'DWM mangler' if dwm is None else 'samsvar' if dwm == value else 'avvik')
                rows.append({'scope': scope, 'archive_part': matched['title'] if matched else title,
                             'archive_part_system_id': matched['system_id'] if matched else None,
                             'metric_id': fact['metric_id'], 'metric_label': LABELS.get(fact['metric_id'], fact['metric_id']),
                             'dwm_value': dwm, 'kdrs_value': value, 'comparison': relation,
                             'kdrs_type': typ, 'test_id': test_id,
                             'source_import_id': resource.get('source_import_id'),
                             'source_file': resource.get('source_file'),
                             'source_sha256': resource.get('source_sha256'),
                             'source_line': line.get('line_number'),
                             'archive_part_index_source_only': resource.get('archive_part_index')})
    return rows


def build_source_comparison(rows, *, evidence_by_job=None):
    """Build a single structured comparison, independently for every selected job."""
    result = {'schema': 'ikamr.noark5.source_comparison.a18.v1', 'jobs': [],
              'policy': ('Kildene beholdes separat. KDRS eksakte observasjoner kan avstemmes, '
                         'men overstyrer ikke DWM. Arkade 5-kjøringer kan ikke summeres '
                         'til unike feil. Arkade tester på uttrekksnivå tilordnes ikke arkivdeler.')}
    evidence_by_job = evidence_by_job or {}
    for job, data, path, diagnostic in rows:
        job_id = str(job.job_id)
        evidence = evidence_by_job.get(job_id)
        if evidence is None:
            evidence = collect_job_evidence(job, data)
        dwm = _dwm_tests(data)
        dwm_ids = {str(t['test_id']): t for t in dwm if t.get('test_id')}
        arkade_runs = _arkade_rows(evidence)
        identity_warnings = source_identity_warnings(job, arkade_runs)
        arkade_controls = defaultdict(dict)
        for run in arkade_runs:
            for test in run['tests']:
                if test.get('id'):
                    # Stable, per-import status: multiple Arkade runs never collapse.
                    arkade_controls[str(test['id'])][str(run['import_id'])] = test
        controls = []
        for test_id in sorted(arkade_controls):
            per_run = arkade_controls[test_id]
            candidates = sorted({str(candidate) for test in per_run.values()
                                 for candidate in test.get('dwm_candidates') or []})
            controls.append({'control_id': test_id,
                             'name': next((t.get('name') for t in per_run.values() if t.get('name')), None),
                             'per_run': dict(per_run),
                             'dwm_test_ids': candidates,
                             'dwm_results': [dwm_ids[c] for c in candidates if c in dwm_ids],
                             'mapping_status': 'kandidat – ikke likestilt kontroll' if candidates else 'ingen DWM-kobling'})
        resources = list((evidence.get('kdrs_query') or {}).get('resources') or [])
        kdrs = _kdrs_exact_observations(resources, data)
        # Count cases without conflating results from different imports/runs.
        relations = Counter(r['comparison'] for r in kdrs)
        result['jobs'].append({'job_id': job_id, 'extraction': str(getattr(job, 'source_extraction', '') or getattr(job, 'name', '') or job_id),
                               'depot_source_path': str(path) if path else None, 'depot_diagnostic': diagnostic,
                               'dwm_xpath': {'summary': ((data or {}).get('technical_validation') or {}).get('summary') or {},
                                             'tests': dwm},
                               'arkade5_runs': arkade_runs,
                               'source_identity_warnings': identity_warnings,
                               'arkade5_control_matrix': controls,
                               'kdrs_query': {'resources': len(resources), 'exact_comparisons': kdrs,
                                              'comparison_status': dict(relations)},
                               'evidence_diagnostics': evidence.get('diagnostics') or []})
    return result


def render_source_comparison_whole_counts(model):
    """Show independent Standard and U1 observations in the MAIN report.

    External observations are never promoted to selected/main values here.
    Multiple distinct readings for the same metric within one source are
    marked as a conflict instead of silently taking one value.
    """
    visible = []
    for entry in model.get('jobs') or []:
        readings = [r for r in ((entry.get('kdrs_query') or {}).get('exact_comparisons') or [])
                    if r.get('scope') == 'uttrekk' and
                    str(r.get('kdrs_type') or '').lower() in ('standard', 'u01', 'u1')]
        if not readings:
            continue
        for metric_id, label in REPORT_METRICS:
            subset = [r for r in readings if r.get('metric_id') == metric_id]
            if not subset:
                continue
            dvals = {r.get('dwm_value') for r in subset if _count(r.get('dwm_value')) is not None}
            columns = []
            detected = []
            for source in ('standard', 'u01'):
                values = {r.get('kdrs_value') for r in subset
                          if ('u01' if r.get('kdrs_type') == 'u1' else r.get('kdrs_type')) == source
                          and _count(r.get('kdrs_value')) is not None}
                columns.append('Motstrid' if len(values) > 1 else next(iter(values)) if values else '–')
                if len(values) == 1:
                    detected.append(next(iter(values)))
            status = ('Motstrid mellom kilder' if any(x == 'Motstrid' for x in columns)
                      or len(set(detected)) > 1 else
                      'Samsvar Standard/U1' if len(detected) == 2 else 'Én KDRS-kilde')
            if len(dvals) > 1:
                status += '; motstrid i DWM'
            elif len(dvals) == 1 and detected and any(v != next(iter(dvals)) for v in detected):
                status += '; avvik mot DWM'
            elif not dvals:
                status += '; DWM mangler'
            visible.append((entry['job_id'], label,
                            next(iter(dvals)) if len(dvals) == 1 else 'Ukjent',
                            *columns, status))
    if not visible:
        return '<p>Ingen eksakt definerte Standard/U1-måltall i importert KDRS-evidens.</p>'
    return ('<p>Standard og U1 vises side om side med DWM. KDRS-verdiene er '
            '<strong>observerte eksterne måltall</strong>, ikke automatisk valgte '
            'rapportverdier. Identiske tall fra flere kilder summeres ikke. '
            'Kildelinje, import og SHA-256 finnes i vedlegg C.</p>' +
            _table(('Jobb','Måltall','DWM','KDRS Standard','KDRS U1',
                    'Kildeavstemming'), visible))


def render_source_comparison_overview(model):
    rows = []
    for job in model.get('jobs') or []:
        summary = (job.get('dwm_xpath') or {}).get('summary') or {}
        runs = job.get('arkade5_runs') or []
        comparisons = (job.get('kdrs_query') or {}).get('comparison_status') or {}
        rows.append((job['job_id'], summary.get('ok', 'Ukjent'), summary.get('error', 'Ukjent'),
                     len(runs), ' / '.join(str(run['error_count']) if run.get('error_count') is not None else 'Ukjent' for run in runs) or '–',
                     (job.get('kdrs_query') or {}).get('resources'),
                     comparisons.get('samsvar', 0), comparisons.get('avvik', 0),
                     comparisons.get('DWM mangler', 0), comparisons.get('ikke_tilordnet', 0)))
    warnings=[(j['job_id'], w['status'], w['source_file'])
              for j in model.get('jobs') or []
              for w in j.get('source_identity_warnings') or []]
    notice=('<h3>Kildeidentitet – kontrollmerknad</h3>'+
            _table(('Jobb','Merknad','Kildefil'), warnings)) if warnings else ''
    return ('<p>DWM XPath, hver Arkade 5-kjøring og KDRS Query er vist som separate kilder. '
            'Arkade-feil per import er ikke antall unike feil; KDRS-tall er observasjoner, '
            'ikke automatisk godkjente rapportverdier.</p>' +
            _table(('Jobb','DWM XPath OK','DWM XPath feil','Arkade-importer',
                    'Arkade-feil per import','KDRS-seksjoner','Tall i samsvar','Tall i avvik',
                    'KDRS-tall uten DWM','U2 uten arkivdelkobling'), rows) + notice)


def render_source_comparison_annex(model, *, level='Medium'):
    out = ['<h2>Felles kontroll- og måltallssammenstilling – DWM / Arkade 5 / KDRS Query</h2>',
           '<p>Kildespesifikke resultater beholdes adskilt. To Arkade-importer vises som to kjøringer. '
           'U2 kobles kun ved entydig arkivdeltittel. Sammenfallende testnumre er ikke bevis for semantisk likhet. '
           'Originale resultatlinjer, kildefil og SHA-256 finnes i JSON-evidensen.</p>']
    for job in model.get('jobs') or []:
        out.append('<h3>' + _h(job['job_id']) + ' – kildematrise</h3>')
        if job.get('source_identity_warnings'):
            out.append('<h4>Kontroll av ekstern kildeidentitet</h4>')
            out.append(_table(('Kilde','Import','Kildefil','Jobbens delserie','Kildefilens delserie','Merknad'), [
                (w.get('source'),w.get('import_id'),w.get('source_file'),
                 w.get('job_subseries'),w.get('file_subseries'),w.get('status'))
                for w in job['source_identity_warnings']]))
            out.append('<p>Kildefilnavn alene dokumenterer ikke feil import. Kildepakken må kontrolleres før resultatene tilordnes faglig.</p>')
        dwm = (job.get('dwm_xpath') or {}).get('tests') or []
        out.append('<h4>DWM XPath – intern teststatus</h4>')
        out.append(_table(('Test-ID', 'Kontrollpunkt', 'Status'),
                          [(t.get('test_id'), t.get('test_point'), t.get('status')) for t in dwm]) if dwm else
                   '<p>Ingen DWM XPath-testresultater i depotrapporten (ukjent, ikke null).</p>')
        runs = job.get('arkade5_runs') or []
        if not runs:
            out.append('<p>Arkade 5: Ingen import dokumentert i dette grunnlaget.</p>')
        else:
            out.append('<h4>Arkade 5 – uavhengige kjøringer</h4>')
            out.append(_table(('Import', 'Versjon', 'Testdato', 'Kildefil', 'SHA-256', 'Feil'),
                              [(r.get('import_id'), r.get('source_version'), r.get('test_date'),
                                r.get('source_file'), r.get('source_sha256'), r.get('error_count')) for r in runs]))
            columns = ['Kontroll', 'Beskrivelse'] + ['Arkade ' + str(r.get('import_id')) for r in runs] + ['DWM-kandidater / status']
            control_rows = []
            for c in job.get('arkade5_control_matrix') or []:
                statuses = [c['per_run'].get(str(run.get('import_id'))) for run in runs]
                if level != 'Full' and all((not st or str(st.get('status') or '').lower() in ('ok','passed','success'))
                                           for st in statuses) and c.get('dwm_results'):
                    continue
                formatted = []
                for st in statuses:
                    formatted.append((str(st.get('status') or 'Ukjent') + ' (' + str(st.get('errors') if st.get('errors') is not None else '?') + ' feil)') if st else 'Ikke registrert')
                target = ', '.join(t.get('test_id') + ': ' + str(t.get('status') or 'ukjent') for t in c['dwm_results'])
                control_rows.append((c.get('control_id'), c.get('name'), *formatted, target or 'Ingen bekreftet DWM-dekning'))
            out.append('<h4>Arkade-kontroller per kjøring</h4>')
            out.append(_table(columns, control_rows) if control_rows else '<p>Ingen avvikende/eksterne Arkade-kontroller å vise på dette detaljnivået.</p>')
        # Relevant Arkade messages from each independent run. Full source result
        # records remain available in the JSON evidence (never silently omitted).
        for run in runs:
            findings = []
            total_findings = 0
            for test in run.get('tests') or []:
                err = test.get('errors')
                noteworthy = str(test.get('status') or '').lower() not in ('ok', 'success', 'passed')
                noteworthy = noteworthy or (isinstance(err, int) and err > 0) or (str(err).isdigit() and int(err)>0)
                if not noteworthy:
                    continue
                for finding in test.get('results') or []:
                    total_findings += 1
                    if len(findings) >= 35:
                        continue
                    if isinstance(finding, dict):
                        location = finding.get('location') or {}
                        if isinstance(location, dict):
                            location = location.get('string') or location.get('file_name') or location.get('source_raw') or ''
                        findings.append((test.get('id'), finding.get('result_type') or test.get('status'),
                                         finding.get('message') or finding.get('text') or '',
                                         str(location)))
                    else:
                        findings.append((test.get('id'), test.get('status'), str(finding), ''))
            if findings:
                out.append('<h4>Arkade 5 – konkrete funn (' + _h(run.get('import_id')) + ')</h4>')
                out.append(_table(('Test','Resultattype','Melding','Plassering'), findings))
                if total_findings > len(findings):
                    out.append('<p>Viser ' + str(len(findings)) + ' av ' + str(total_findings) +
                               ' funn for denne kjøringen. Fullstendige resultatobjekter er bevart i JSON-evidensen.</p>')
            elif any(str(t.get('status') or '').lower() not in ('ok','success','passed')
                     for t in run.get('tests') or []):
                out.append('<p>Arkade-import ' + _h(run.get('import_id')) +
                           ': kontrollstatus indikerer funn, men detaljerte meldinger finnes ikke i dette grunnlaget.</p>')
        comparisons = ((job.get('kdrs_query') or {}).get('exact_comparisons') or [])
        out.append('<h4>KDRS Query – eksakt definerte måltall mot DWM XPath</h4>')
        if not comparisons:
            out.append('<p>Ingen eksakte, sammenlignbare KDRS-måltall dokumentert. Dette betyr ikke null aktivitet.</p>')
        else:
            out.append(_table(('Omfang', 'Arkivdel', 'Måltall', 'DWM XPath', 'KDRS Query',
                               'Avstemming', 'KDRS-type', 'Import', 'Kildefil', 'Kildelinje'),
                              [(r['scope'], r.get('archive_part'), r['metric_label'],
                                r['dwm_value'] if r['dwm_value'] is not None else 'Ukjent', r['kdrs_value'],
                                r['comparison'], r['kdrs_type'], r['source_import_id'],
                                r['source_file'], r['source_line']) for r in comparisons]))
        for warning in job.get('evidence_diagnostics') or []:
            out.append('<p>' + _h(warning) + '</p>')
    return ''.join(out)
