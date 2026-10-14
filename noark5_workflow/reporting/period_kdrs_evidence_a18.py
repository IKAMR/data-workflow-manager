"""Read-only KDRS Query period/year evidence, separate from DWM XPath results.

Historical Standard/U1/U2 imports remain separate; different imports and scopes
are NEVER combined to infer an archive period or a DWM XPath result.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .external_report_a18 import _work_source

# The precise, definition-backed annual facts created by kdrs_query_semantics.
# Change-log activity is NOT part of an archival production period.
YEAR_METRICS = {
    'folders_by_creation_year': 'Mapper/saker (opprettet)',
    'registrations_by_creation_year': 'Registreringer (opprettet)',
    'journalposts_by_journal_year': 'Journalposter (journaldato)',
    'running_journal_by_year': 'Løpende journal (journaldato)',
    'public_journal_by_year': 'Offentlig journal (journaldato)',
    'change_log_events_by_year': 'Endringslogg (ikke arkivperiode)',
}
PERIOD_METRICS = frozenset(YEAR_METRICS) - {'change_log_events_by_year'}


def _positive_year(year: Any, quantity: Any) -> tuple[int, int] | None:
    try:
        y, count = int(year), int(quantity)
    except (TypeError, ValueError):
        return None
    if not 1000 <= y <= 9999 or count < 0:
        return None
    return y, count


def _scope_key(line: dict, resource: dict) -> tuple[str, str]:
    """The U2 scope is its own numbered source part, not a DWM archive-part ID."""
    number = line.get('archive_part_index')
    if number is None:
        number = resource.get('archive_part_index')
    title = str(line.get('archive_part_title') or resource.get('archive_part_title') or '').strip()
    if number is None and not title:
        return 'whole', 'Hele uttrekket'
    if number is not None:
        try:
            number = int(number)
        except (ValueError, TypeError):
            number = str(number)
    return f'u2:{number}:{title}', f'U2 arkivdel {number if number is not None else "?"}: {title or "(uten tittel)"}'


def period_evidence_from_pool(pool: dict[str, Any]) -> dict[str, Any]:
    """Create display-only distributions, preserving every import/report-type scope.

    If two different source lines disagree about one year, store both observations
    and flag the conflict. Never sum them or choose a hidden winner.
    """
    runs: dict[tuple[str, str], dict] = {}
    for resource in pool.get('resources') or []:
        report_type = str(resource.get('report_type') or '')
        if report_type not in ('standard', 'u01', 'u02'):
            continue
        import_id = str(resource.get('import_id') or '')
        key = (import_id, report_type)
        run = runs.setdefault(key, {
            'import_id': import_id,
            'report_type': report_type,
            'sources': set(),
            'scopes': {},
        })
        source_file = str(resource.get('source_file') or '').strip()
        if source_file:
            run['sources'].add(source_file)
        for line in resource.get('semantic_lines') or []:
            if not isinstance(line, dict):
                continue
            scope_id, scope_label = _scope_key(line, resource)
            for fact in line.get('facts') or []:
                if (not isinstance(fact, dict)
                        or fact.get('mapping_status') != 'exact'
                        or fact.get('value_kind') != 'year_count'
                        or fact.get('metric_id') not in YEAR_METRICS):
                    continue
                valid = _positive_year(fact.get('year'), fact.get('value'))
                if valid is None:
                    continue
                year, count = valid
                scope = run['scopes'].setdefault(scope_id, {
                    'scope_id': scope_id,
                    'label': scope_label,
                    'series': {},
                })
                metric = fact['metric_id']
                bucket = scope['series'].setdefault(metric, {})
                bucket.setdefault(year, set()).add(count)
    output = []
    for (import_id, report_type), run in runs.items():
        scopes = []
        for scope in run['scopes'].values():
            series = {}
            disagreements = []
            years = set()
            for metric, counts in scope['series'].items():
                rows = {}
                for year, values in sorted(counts.items()):
                    if len(values) != 1:
                        disagreements.append(f'{YEAR_METRICS[metric]} {year}: ulike KDRS-verdier')
                        rows[str(year)] = None
                    else:
                        rows[str(year)] = next(iter(values))
                    if metric in PERIOD_METRICS and rows[str(year)] is not None and rows[str(year)] > 0:
                        years.add(year)
                series[metric] = rows
            scopes.append({'scope_id': scope['scope_id'], 'label': scope['label'],
                           'series': series, 'conflicts': disagreements,
                           'period_observed_years': [min(years), max(years)] if years else None})
        output.append({'import_id': import_id, 'report_type': report_type,
                       'sources': sorted(run['sources']), 'scopes': scopes})
    return {'kind': 'kdrs_query_period_evidence', 'data_role': 'external_evidence_only',
            'runs': output,
            'note': 'Importert KDRS-evidens er ikke DWM XPath eller faglig godkjent periode.'}


def load_job_kdrs_period_evidence(job) -> dict[str, Any]:
    """Read only the specified job's imported KDRS data. No import or execution."""
    missing = {'kind': 'kdrs_query_period_evidence',
               'data_role': 'external_evidence_only', 'runs': [], 'diagnostics': []}
    work = _work_source(job)
    if work is None or not (Path(work) / 'external_evidence' / 'kdrs_query').is_dir():
        missing['diagnostics'].append('Ingen importerte KDRS Query-resultater funnet for denne jobben.')
        return missing
    try:
        from noark5_workflow.external_evidence.kdrs_query_mapping import build_mapped_pool
        result = period_evidence_from_pool(build_mapped_pool(work))
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        missing['diagnostics'].append('KDRS Query kunne ikke leses: ' + str(exc))
        return missing
    if not any(run['scopes'] for run in result['runs']):
        result.setdefault('diagnostics', []).append(
            'KDRS Query er importert, men ingen entydig tolket årsfordeling finnes.')
    return result


def format_kdrs_scope(run: dict, scope: dict) -> list[str]:
    """Detailed readable evidence with source and distinct metric identity."""
    result = [f"KDRS Query {run.get('report_type')} – {scope.get('label')}",
              'Import-ID: ' + str(run.get('import_id') or '–'),
              'Kilde: ' + ('; '.join(run.get('sources') or []) or '–')]
    for metric, years in (scope.get('series') or {}).items():
        result.append(YEAR_METRICS.get(metric, metric) + ':')
        for year, value in sorted(years.items()):
            result.append('  ' + str(year) + ': ' + ('Konflikt' if value is None else str(value)))
    span = scope.get('period_observed_years')
    result.append('Observerte ytterår i denne KDRS-kilden: ' + (
        f'{span[0]}–{span[1]}' if span else 'Ikke tilgjengelig'))
    result.extend(scope.get('conflicts') or [])
    result.append('KDRS Query gir separat evidens, ikke automatisk DWM- eller depotgodkjenning.')
    return result


def summarize_kdrs_period_sources(runs: list[dict[str, Any]]) -> list[str]:
    """Short source index for period dialog; never sums or merges source runs.

    The full year distributions remain available by selecting each source in the
    dropdown. U2 counts are scope counts, not DWM archive-part counts.
    """
    lines: list[str] = []
    for run in runs:
        import_id = str(run.get('import_id') or 'ukjent import')
        report_type = str(run.get('report_type') or 'ukjent type')
        scopes = run.get('scopes') or []
        whole = [s for s in scopes if s.get('scope_id') == 'whole']
        for scope in whole:
            span = scope.get('period_observed_years')
            period = f'{span[0]}–{span[1]}' if isinstance(span, (list, tuple)) and len(span) == 2 else 'ikke tilgjengelig'
            lines.append(f'  {report_type} / Hele uttrekket: {period} (import {import_id})')
            if scope.get('conflicts'):
                lines.append(f'    Motstridende årstall: {len(scope["conflicts"])}')
        part_scopes = [s for s in scopes if s.get('scope_id') != 'whole']
        if part_scopes:
            lines.append(f'  {report_type}: {len(part_scopes)} arkivdelvise kildeområder (import {import_id})')
        if not scopes:
            lines.append(f'  {report_type}: ingen entydige årstall (import {import_id})')
    return lines
