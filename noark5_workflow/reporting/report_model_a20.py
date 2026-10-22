"""Canonical read-only model shared by all a20 selected-job report outputs.

This module consumes the *existing* a19 report-package JSON. It does not
re-run analyses, infer missing quantities, associate KDRS U2 by list position,
or replace either DWM values or externally imported observations.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

SCHEMA = 'ikamr.noark5.report_snapshot.a20.v1'
METRICS = (
    ('archive_part_count', 'Arkivdeler'),
    ('folder_count', 'Mapper'),
    ('registration_count', 'Registreringer'),
    ('journalpost_count', 'Journalposter'),
    ('document_description_count', 'Dokumentbeskrivelser'),
    ('document_object_count', 'Dokumentobjekter'),
)


def _count(value: Any) -> int | None:
    """A missing value is *never* 0, and booleans are not a count."""
    return value if type(value) is int and value >= 0 else None


def _safe_years(value: Any) -> list[int] | None:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        return None
    try:
        first, last = int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None
    return [first, last] if 1000 <= first <= last <= 9999 else None


def _period_status(period: dict) -> str:
    """Source-aware *professional* status; never the XPath-only status.

    DWM XPath availability and the possibility of a professional assessment
    are different questions. This label never implicitly approves a period.
    """
    saved = period.get('assessment_status')
    if saved == 'godkjent' and _safe_years(period.get('approved_years')):
        return 'Godkjent – faglig vurdert'
    if saved == 'undersokes':
        return 'Under undersøkelse'
    if saved == 'godkjent':
        return 'Godkjenning må kontrolleres (mangler gyldige ytterår)'
    if _safe_years(period.get('dwm_observed_years')):
        return 'Krever faglig vurdering – DWM XPath tilgjengelig'
    has_kdrs_years = any(
        scope.get('scope_id') == 'whole' and _safe_years(scope.get('period_observed_years'))
        for run in period.get('kdrs_runs') or []
        for scope in run.get('scopes') or []
    )
    if has_kdrs_years:
        return 'Krever faglig vurdering – KDRS Query tilgjengelig'
    if period.get('kdrs_runs'):
        return 'Krever faglig vurdering – KDRS Query uten entydig årsgrunnlag'
    return 'Manglende årsgrunnlag – faglig vurdering mulig'


def _part_status(part: dict) -> str:
    if part.get('status') == 'godkjent' and _safe_years(part.get('approved_years')):
        return 'Godkjent'
    if part.get('status') == 'undersokes':
        return 'Under undersøkelse'
    return 'Ikke faglig godkjent'


def _source_index(period: dict) -> list[dict]:
    result = []
    for run in period.get('kdrs_runs') or []:
        result.append({
            'report_type': run.get('report_type'),
            'import_id': run.get('import_id'),
            'source_files': list(run.get('source_files') or []),
            'whole_years': [
                years for scope in run.get('scopes') or []
                if scope.get('scope_id') == 'whole'
                for years in [_safe_years(scope.get('period_observed_years'))]
                if years is not None
            ],
            'part_scope_count': sum(scope.get('scope_id') != 'whole'
                                    for scope in run.get('scopes') or []),
        })
    return result


def _native_parts(data: dict, period: dict) -> list[dict]:
    assessments = {str(p.get('system_id')): p
                   for p in period.get('archive_parts') or [] if p.get('system_id')}
    result = []
    for no, source in enumerate(data.get('archive_parts') or [], 1):
        identity = (source or {}).get('archive_part') or {}
        sid = str(identity.get('system_id') or '')
        saved = assessments.get(sid, {}) if sid else {}
        result.append({
            'number': no, 'system_id': sid or None,
            'title': str(identity.get('title') or sid or 'Uten navn'),
            'counts': {metric: _count((source or {}).get(metric))
                       for metric, _label in METRICS if metric != 'archive_part_count'},
            'assessment_status': saved.get('status', 'ikke_vurdert'),
            'professional_status': _part_status(saved) if sid else 'Mangler entydig system-ID',
            'approved_years': _safe_years(saved.get('approved_years')),
            'selected_years': _safe_years(saved.get('selected_years')),
            'dwm_observed_years': _safe_years(saved.get('dwm_observed_years')),
            'comment': str(saved.get('comment') or ''),
            'source_note': str(saved.get('source_note') or ''),
        })
    return result


def _unique_key(entry: dict) -> tuple[str, str]:
    """Job ID is local to a job list; path is essential for diagnostics."""
    source = entry.get('source_file')
    if source:
        return str(entry.get('job_id')), str(source).replace('\\', '/').casefold()
    return str(entry.get('job_id')), str(entry.get('extraction'))


def build_snapshot(package: dict) -> dict:
    """Build one canonical compact model for HTML, PDF, JSON and CSV.

    Input is the existing report_package_a16 JSON contract, including the
    period_source_evidence produced by period_report_a18. No job is read again.
    """
    raw_jobs = package.get('jobs') or []
    period_jobs = ((package.get('period_source_evidence') or {}).get('jobs') or [])
    warnings = []
    if len(period_jobs) != len(raw_jobs):
        warnings.append('Periodekilder og jobber har ulikt antall; ingen kilder kobles ved gjetning.')
    result = []
    totals = {key: {'dwm_sum': 0, 'with_dwm_value': 0, 'missing_dwm_value': 0}
              for key, _label in METRICS}
    seen: set[tuple[str,str]] = set()
    ids = Counter(str(j.get('job_id')) for j in raw_jobs)
    if any(v > 1 for v in ids.values()):
        warnings.append('JOB-nnn er ikke globalt unik. Kontroller kilde og arbeidsområde for like ID-er.')
    for i, job in enumerate(raw_jobs):
        data = job.get('depot_report') or {}
        period = (period_jobs[i] if i < len(period_jobs) else {}) or {}
        # Only use the i-th period item when the job identity agrees.
        if period and str(period.get('job_id')) != str(job.get('job_id')):
            warnings.append('Kildeidentitet stemmer ikke for ' + str(job.get('job_id')) + '; periodeevidens vises ikke.')
            period = {}
        identity = _unique_key(job)
        if identity in seen:
            warnings.append('Samme rapportkilde er valgt mer enn én gang: ' + str(job.get('job_id')))
            # Do not double count or duplicate the same source in the a20 summary.
            continue
        seen.add(identity)
        summary = data.get('summary') or {}
        counts = {key: _count(summary.get(key)) for key, _label in METRICS}
        for key, value in counts.items():
            if value is None:
                totals[key]['missing_dwm_value'] += 1
            else:
                totals[key]['with_dwm_value'] += 1
                totals[key]['dwm_sum'] += value
        parts = _native_parts(data, period)
        if counts['archive_part_count'] is not None and parts and counts['archive_part_count'] != len(parts):
            warnings.append(str(job.get('job_id')) + ': rapportert antall arkivdeler stemmer ikke med radene.')
        result.append({
            'job_id': str(job.get('job_id') or ''),
            'extraction': str(job.get('extraction') or job.get('job_id') or ''),
            'source_file': job.get('source_file'),
            'diagnostic': str(job.get('diagnostic') or ''),
            'has_depot_report': bool(job.get('depot_report')),
            'counts': counts, 'archive_parts': parts,
            'reported_archive_parts': len(parts),
            'professional_period_status': _period_status(period),
            'assessment_status': period.get('assessment_status', 'ikke_vurdert'),
            'approved_years': _safe_years(period.get('approved_years')),
            'selected_years': _safe_years(period.get('selected_years')),
            'dwm_observed_years': _safe_years(period.get('dwm_observed_years')),
            'dwm_declared_years': _safe_years(period.get('dwm_declared_years')),
            'professional_comment': str(period.get('comment') or ''),
            'kdrs_sources': _source_index(period),
            'kdrs_diagnostics': list(period.get('kdrs_diagnostics') or []),
        })
    return {
        'schema': SCHEMA,
        'number_selected': len(raw_jobs),
        'number_distinct': len(result),
        'with_depot_report': sum(bool(j['has_depot_report']) for j in result),
        'archive_part_rows': sum(len(j['archive_parts']) for j in result),
        'totals': totals,
        'jobs': result,
        'warnings': warnings,
        'policy': ('DWM XPath, KDRS Query og Arkade 5 er separate evidenskilder. '
                   'Ukjent er ikke null. Produksjonsperioder godkjennes bare manuelt.'),
    }
