"""Read-only period evidence for one or more selected Noark 5 jobs.

The DWM XPath period and the imported KDRS Query year distributions are
independent sources. A KDRS observation never becomes an approved period or a
DWM result merely because it appears in this report.
"""
from __future__ import annotations

from html import escape
from typing import Any

from .period_assessment_a16 import review_candidate
from .period_kdrs_evidence_a18 import (
    YEAR_METRICS,
    format_kdrs_scope,
    load_job_kdrs_period_evidence,
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


def collect_period_sources(rows) -> dict[str, Any]:
    """Build the identical structured source for 1 or N jobs, without writes.

    rows follow report_package_a16: (job, native_report, report_path, diagnostic).
    All KDRS year observations stay grouped by their original import/type/scope.
    """
    jobs = []
    for job, data, path, diagnostic in rows:
        candidate = review_candidate(data)
        kdrs = load_job_kdrs_period_evidence(job)
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
                'import_id': source.get('import_id'),
                'report_type': source.get('report_type'),
                'source_files': list(source.get('sources') or []),
                'scopes': scopes,
            })
        jobs.append({
            'job_id': str(job.job_id),
            'dwm_report_file': str(path) if path else None,
            'dwm_report_diagnostic': diagnostic,
            'dwm_observed_years': candidate.get('observed_years'),
            'dwm_declared_years': candidate.get('declared_years'),
            'dwm_review_status': candidate.get('evaluation_status'),
            'kdrs_runs': runs,
            'kdrs_diagnostics': list(kdrs.get('diagnostics') or []),
        })
    return {
        'schema': 'ikamr.noark5.period_sources.a18.v1',
        'data_role': 'read_only_comparison',
        'policy': 'No implicit merge of DWM and KDRS year ranges, and no automatic depot approval.',
        'jobs': jobs,
    }


def render_period_source_overview(model: dict) -> str:
    """Compact cross-source presence status in the main report."""
    entries = []
    for item in model.get('jobs') or []:
        runs = item.get('kdrs_runs') or []
        scopes = [s for run in runs for s in run.get('scopes') or []]
        periods = sum(bool(s.get('period_observed_years')) for s in scopes)
        conflicts = sum(len(s.get('conflicts') or []) for s in scopes)
        if not runs:
            kdrs = 'Ingen importerte årsserier dokumentert'
        else:
            kdrs = f'{len(runs)} import-/rapportkilder; {periods} med observerte ytterår'
            if conflicts:
                kdrs += f'; {conflicts} motstridende årsobservasjoner'
        entries.append((
            item.get('job_id'),
            _span(item.get('dwm_declared_years')),
            _span(item.get('dwm_observed_years')),
            kdrs,
            'Kan ikke vurderes – mangler DWM XPath' if not item.get('dwm_observed_years')
            else 'Separat evidens – ingen automatisk periodeavstemming',
        ))
    return ('<p>DWM XPath og KDRS Query vises hver for seg. KDRS-ytterår er ikke '
            'automatisk godkjent arkivperiode. Null årsserier betyr ikke null aktivitet.</p>'
            + _table(('Jobb', 'Oppgitt periode', 'DWM XPath', 'KDRS Query', 'Kildestatus'), entries))


def render_period_source_annex(model: dict) -> str:
    """Report appendix D: all unambiguous imported annual facts and provenance."""
    output = ['<h2>KDRS Query – importerte årsserier og periodeevidens</h2>',
              '<p>Opprinnelige DWM XPath-resultater og KDRS Query Standard/U1/U2 holdes adskilt. '
              'Verdier fra ulike importkjøringer eller arkivdeler summeres ikke. '
              'Endringslogg gir ikke automatisk arkivperiode. Ingen ny analyse utføres.</p>']
    for item in model.get('jobs') or []:
        output.append('<h3>' + _h(item.get('job_id')) + ' – datakilder</h3>')
        output.append(_table(('Oppgitt periode', 'DWM XPath', 'Kildestatus'), [(
            _span(item.get('dwm_declared_years')),
            _span(item.get('dwm_observed_years')),
            'Kan ikke vurderes – DWM XPath mangler' if not item.get('dwm_observed_years')
            else 'XPath tilgjengelig',
        )]))
        for diagnostic in item.get('kdrs_diagnostics') or []:
            output.append('<p class="muted">' + _h(diagnostic) + '</p>')
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
