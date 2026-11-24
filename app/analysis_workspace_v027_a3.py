"""Read-only filters and annual chart projection for the v0.2.7-a3 Analyse GUI.

The report's stored observations are authoritative.  UI categories are not
normative Noark approvals.  No source, Work result, or decision is written.
"""
from __future__ import annotations

from typing import Any

from app.analysis_workspace_v027_a2 import (
    AnalysisSnapshot, METRICS, annual_rows, part_identity,
    rule_findings, selected_parts,
)

FILTERS = (
    ('Alle', 'all'),
    ('Feil / avvik', 'error'),
    ('Advarsler', 'warning'),
    ('Til vurdering', 'review'),
    ('Ofte sjekket', 'favorite'),
)

# Three meaningful families, five *independent* date series.
ANNUAL_FAMILIES = (
    ('Mapper / saker', ('folder',)),
    ('Registreringer / journalposter', ('registration', 'journal')),
    ('Dokumentbeskrivelser / dokumentobjekter',
     ('document_description', 'document_object')),
)


def annual_chart_data(snapshot: AnalysisSnapshot,
                      part_index: int | None = None,
                      year: str = '') -> tuple[dict[str, int | None], ...]:
    """Reuse A2's report-backed year series, never merge distinct date fields."""
    return tuple({'year': int(y), **dict(zip((key for key, _ in METRICS), counts))}
                 for y, counts in annual_rows(snapshot, part_index, year))


def favorite_key(snapshot: AnalysisSnapshot, kind: str, payload: Any) -> str:
    """Stable identity for a control, not a file path or display-row number."""
    if kind == 'metadata':
        return 'metadata:' + str(payload.get('metadata_id') or '')
    if kind == 'format':
        return 'format:' + str(payload.get('puid') or '')
    if kind == 'year':
        return 'year:' + str(payload)
    if kind in ('part', 'preservation'):
        try:
            ident = part_identity(snapshot.parts[payload])
        except (IndexError, TypeError, KeyError):
            return ''
        native_id = str(ident.get('system_id') or '')
        return kind + ':' + native_id if native_id else ''
    if kind == 'period_finding':
        return 'period:' + str(payload.get('category') or '') + ':' + str(
            (payload.get('year_evidence') or {}).get('year') or '')
    return ''


def result_state(snapshot: AnalysisSnapshot, kind: str, payload: Any,
                 part_index: int | None = None) -> tuple[str, str]:
    """Return (filter category, visible label). Do not infer normative approval."""
    if kind == 'metadata':
        deviations = payload.get('deviations')
        if isinstance(deviations, int) and deviations > 0:
            return 'error', 'Avvik – faglig vurdering'
        if deviations == 0:
            return 'none', 'Ingen avvik registrert'
        return 'unknown', 'Ikke avklart'
    if kind == 'period_finding':
        severity = str(payload.get('severity') or '').casefold()
        return ('error', 'Avvik – faglig vurdering') if severity == 'serious' else (
            'warning', 'Vurderingspunkt')
    if kind == 'part' and snapshot.findings_complete:
        chosen = selected_parts(snapshot, payload)
        if len(chosen) != 1:
            return 'unknown', 'Uavklart'
        ident = str(part_identity(chosen[0]).get('system_id') or '')
        if ident and any(str(f.get('archive_part_id') or '') == ident
                         for f in snapshot.findings):
            return 'review', 'Metadataavvik til vurdering'
    # A count or identified format does not prove validity or acceptance.
    return 'unknown', 'Ingen egen vurdering'


def matches_filter(category: str, filter_key: str,
                   favorite: bool = False) -> bool:
    if filter_key == 'all':
        return True
    if filter_key == 'favorite':
        return favorite
    if filter_key == 'review':
        return category in ('error', 'warning', 'review')
    return category == filter_key


def period_review_rows(snapshot: AnalysisSnapshot, part_index: int | None,
                       year: str = '') -> tuple[dict[str, Any], ...]:
    """Show only findings whose known scope matches; never assign a global
    period warning to a particular archive part without source identity.
    """
    if part_index is not None:
        return ()
    result = []
    for row in snapshot.report.get('deviations') or ():
        if not isinstance(row, dict) or not row.get('requires_review'):
            continue
        category = str(row.get('category') or '')
        if category not in ('period_source_divergence',
                            'document_activity_without_folder_or_journal',
                            'delivery_period_chronology'):
            continue
        finding_year = str((row.get('year_evidence') or {}).get('year') or '')
        if year and finding_year and finding_year != year:
            continue
        if year and not finding_year:
            # Undated, global difference cannot be narrowed to a chosen year.
            continue
        result.append(row)
    return tuple(result)
