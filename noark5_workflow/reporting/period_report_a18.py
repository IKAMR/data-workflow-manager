"""Read-only period source comparison with operator-approved extraction/part decisions.

KDRS Query Standard, U1 and U2 are independent imported evidence. Neither an
import nor missing DWM XPath silently approves/invalidates an archival period.
"""
from __future__ import annotations

from html import escape
from typing import Any

from .period_assessment_a16 import review_candidate, load_assessment, reviewed_years
from .period_kdrs_evidence_a18 import (
    YEAR_METRICS, format_kdrs_scope, load_job_kdrs_period_evidence,
)


def _h(value: Any) -> str:
    return escape('–' if value is None else str(value), quote=True)


def _table(headers, rows) -> str:
    head = ''.join('<th>' + _h(x) + '</th>' for x in headers)
    body = ''.join('<tr>' + ''.join('<td>' + _h(x) + '</td>' for x in row) + '</tr>' for row in rows)
    return '<table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table>'


def _span(value) -> str:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        return 'Ikke tilgjengelig'
    return str(value[0]) if value[0] == value[1] else f'{value[0]}–{value[1]}'


def _observed_part(data, system_id):
    for row in ((data or {}).get('period_reconciliation') or {}).get('archive_parts') or []:
        if str((row.get('archive_part') or {}).get('system_id')) != str(system_id):
            continue
        span = row.get('observed_period') or {}
        try:
            first, last = int(span['first_year']), int(span['last_year'])
            if 1000 <= first <= last <= 9999:
                return [first, last]
        except (TypeError, ValueError, KeyError):
            pass
    return None


def _native_parts(data, assessment):
    saved_parts = (assessment or {}).get('archive_part_assessments') or {}
    rows = []
    for index, row in enumerate((data or {}).get('archive_parts') or [], 1):
        meta = row.get('archive_part') or {}
        system_id = str(meta.get('system_id') or '')
        saved = saved_parts.get(system_id) or {}
        rows.append({
            'number': index, 'system_id': system_id or None,
            'title': meta.get('title') or system_id or 'Uten navn',
            'dwm_observed_years': _observed_part(data, system_id) if system_id else None,
            'status': saved.get('status', 'ikke_vurdert'),
            'approved_years': list(reviewed_years(saved)) if reviewed_years(saved) else None,
            'selected_years': saved.get('selected_years'),
            'comment': saved.get('comment') or '',
            'source_note': saved.get('source_note') or '',
        })
    return rows


def _source_status(item):
    approved = item.get('approved_years')
    if approved:
        return 'Godkjent – faglig vurdert ' + _span(approved)
    if item.get('assessment_status') == 'undersokes':
        return 'Under undersøkelse'
    has_kdrs_period = any(
        s.get('scope_id') == 'whole' and s.get('period_observed_years')
        for run in item.get('kdrs_runs') or [] for s in run.get('scopes') or [])
    if item.get('dwm_observed_years'):
        return 'Krever faglig vurdering' if item.get('dwm_review_status') == 'vurdering_kreves' else 'Til vurdering – DWM XPath tilgjengelig'
    if has_kdrs_period:
        return 'Krever faglig vurdering – KDRS Query tilgjengelig'
    if item.get('kdrs_runs'):
        return 'Krever faglig vurdering – KDRS Query uten entydige ytterår'
    return 'Mangler observerte ytterår – faglig vurdering mulig'


def collect_period_sources(rows) -> dict[str, Any]:
    """Use one source model for single/multiple job HTML and JSON exports."""
    jobs = []
    for job, data, path, diagnostic in rows:
        candidate = review_candidate(data)
        kdrs = load_job_kdrs_period_evidence(job)
        saved = load_assessment(job) or {}
        runs = []
        for source in kdrs.get('runs') or []:
            scopes = []
            for scope in source.get('scopes') or []:
                scopes.append({
                    'scope_id': scope.get('scope_id'),
                    'label': scope.get('label'),
                    'period_observed_years': scope.get('period_observed_years'),
                    'series': scope.get('series') or {},
                    'conflicts': scope.get('conflicts') or [],
                })
            runs.append({
                'import_id': source.get('import_id'), 'report_type': source.get('report_type'),
                'source_files': list(source.get('sources') or []), 'scopes': scopes,
            })
        jobs.append({
            'job_id': str(job.job_id), 'dwm_report_file': str(path) if path else None,
            'dwm_report_diagnostic': diagnostic,
            'dwm_observed_years': candidate.get('observed_years'),
            'dwm_declared_years': candidate.get('declared_years'),
            'dwm_review_status': candidate.get('evaluation_status'),
            'assessment_status': saved.get('status', 'ikke_vurdert'),
            'approved_years': list(reviewed_years(saved)) if reviewed_years(saved) else None,
            'selected_years': saved.get('selected_years'),
            'comment': saved.get('comment') or '',
            'archive_parts': _native_parts(data, saved),
            'kdrs_runs': runs, 'kdrs_diagnostics': list(kdrs.get('diagnostics') or []),
        })
    return {
        'schema': 'ikamr.noark5.period_sources.a18.v1',
        'data_role': 'read_only_comparison',
        'policy': 'No implicit merge of DWM and KDRS years, and no automatic depot approval.',
        'jobs': jobs,
    }


def render_period_source_overview(model: dict) -> str:
    entries = []
    for item in model.get('jobs') or []:
        runs = item.get('kdrs_runs') or []
        scopes = [s for run in runs for s in run.get('scopes') or []]
        periods = sum(bool(s.get('period_observed_years')) for s in scopes)
        conflicts = sum(len(s.get('conflicts') or []) for s in scopes)
        kdrs = (f'{len(runs)} import-/rapportkilder; {periods} med observerte ytterår'
                if runs else 'Ingen importerte årsserier dokumentert')
        if conflicts:
            kdrs += f'; {conflicts} motstridende årsobservasjoner'
        entries.append((item.get('job_id'), _span(item.get('dwm_declared_years')),
                        _span(item.get('dwm_observed_years')),
                        _span(item.get('approved_years')), kdrs, _source_status(item)))
    return ('<p>DWM XPath og KDRS Query er separate kilder. Observerte år er ikke '
            'automatisk godkjent arkivperiode. Manglende XPath hindrer ikke manuell '
            'faglig vurdering. Null årsserier betyr ikke null aktivitet.</p>'
            + _table(('Jobb', 'Oppgitt periode', 'DWM XPath', 'Faglig vurdert periode',
                      'KDRS Query', 'Vurderingsstatus'), entries))


def render_period_source_annex(model: dict) -> str:
    output = ['<h2>KDRS Query – importerte årsserier og periodeevidens</h2>',
              '<p>DWM XPath, KDRS Standard/U1/U2 og faglig godkjente perioder '
              'holdes atskilt. U2-kildenummer og navn kobles aldri automatisk '
              'til DWM system-ID. Endringslogg er ikke arkivperiode.</p>']
    for item in model.get('jobs') or []:
        output.append('<h3>' + _h(item.get('job_id')) + ' – periodevurdering av hele uttrekket</h3>')
        output.append(_table(('Oppgitt periode', 'DWM XPath', 'Faglig godkjent periode',
                              'Vurderingsstatus'), [(
            _span(item.get('dwm_declared_years')), _span(item.get('dwm_observed_years')),
            _span(item.get('approved_years')), _source_status(item))]))
        if item.get('comment'):
            output.append('<p>Faglig begrunnelse: ' + _h(item['comment']) + '</p>')
        for diagnostic in item.get('kdrs_diagnostics') or []:
            output.append('<p class="muted">' + _h(diagnostic) + '</p>')
        native_parts = item.get('archive_parts') or []
        if native_parts:
            output.append('<h3>' + _h(item.get('job_id')) + ' – periodevurdering per arkivdel</h3>')
            entries = []
            for part in native_parts:
                approved = _span(part.get('approved_years'))
                status = ('Godkjent' if part.get('approved_years') else
                          'Under undersøkelse' if part.get('status') == 'undersokes' else
                          'Ikke faglig godkjent')
                entries.append((part.get('number'), part.get('title'), part.get('system_id') or 'Ukjent',
                                _span(part.get('dwm_observed_years')), approved,
                                status, part.get('comment') or '–'))
            output.append(_table(('#', 'Arkivdel', 'System-ID', 'DWM XPath',
                                  'Faglig vurdert', 'Status', 'Begrunnelse'), entries))
        runs = item.get('kdrs_runs') or []
        if not runs:
            output.append('<p>Ingen KDRS-årsserier er tilgjengelige for denne jobben. '
                          'Dette betyr ikke at arkivinnholdet er tomt.</p>')
            continue
        for run in runs:
            output.append('<h4>KDRS Query ' + _h(run.get('report_type')) +
                          ' – import ' + _h(run.get('import_id')) + '</h4>')
            output.append('<p>Kilde: ' + _h('; '.join(run.get('source_files') or []) or 'Ukjent') + '</p>')
            if not run.get('scopes'):
                output.append('<p>Import registrert, men ingen entydige årsdata tolket for denne rapporttypen.</p>')
            for scope in run.get('scopes') or []:
                output.append('<h4>' + _h(scope.get('label')) + ' – ' +
                              _h(_span(scope.get('period_observed_years'))) + '</h4>')
                observed = []
                for metric, years in (scope.get('series') or {}).items():
                    for year, count in sorted((years or {}).items()):
                        observed.append((YEAR_METRICS.get(metric, metric), year,
                                         'Konflikt' if count is None else count))
                if observed:
                    output.append(_table(('Datokilde / måltall', 'År', 'Antall'), observed))
                else:
                    output.append('<p>Ingen sikre årstall i denne delen.</p>')
                if scope.get('conflicts'):
                    output.append('<p>Motstridende kildeobservasjoner: ' +
                                  _h('; '.join(scope['conflicts'])) + '</p>')
    return ''.join(output)
