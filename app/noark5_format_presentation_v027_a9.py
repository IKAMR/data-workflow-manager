"""A9: PUID format-rule presentation beside (not instead of) professional review.

Sorting occurs over the complete, already aggregated PUID groups before page
selection. Format-rule labels must originate from the selected Setup/GUI policy;
no PRONOM identification is interpreted as automatic depot approval.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.noark5_format_sort_v027_a8 import _natural, sorted_puid_groups


MAIN_COLUMNS_A9 = (
    'Velg', 'PUID', 'Kategori', 'MIME-gruppe', 'Filformat',
    'Filer', 'Kopier', 'Eksporter', 'Formatvurdering', 'Faglig vurdering',
)

PROFESSIONAL_LABELS = {
    'accepted': 'Faglig akseptert',
    'deviation': 'Avvik',
    'clarify': 'Til avklaring',
    '': 'Ikke vurdert',
}


def professional_label(status: Any) -> str:
    """Review metadata; do not infer a professional conclusion from a PUID."""
    return PROFESSIONAL_LABELS.get(status, 'Ukjent')


def format_rule_label(value: Any) -> str:
    """Display the actual policy result, not a guessed MIME-derived status."""
    label = str(value or '').strip()
    return label if label else 'Vurdering ikke tilgjengelig'


def sorted_a9_groups(rows: Iterable[Mapping[str, Any]], *,
                     column: int, descending: bool = False,
                     checked: Mapping[str, bool] | None = None,
                     assessments: Mapping[str, str] | None = None,
                     policy_labels: Mapping[str, str] | None = None) -> tuple[dict[str, Any], ...]:
    """Sort ALL groups, including the new policy and human-review columns."""
    if type(column) is not int or not 0 <= column < len(MAIN_COLUMNS_A9):
        raise ValueError('Ugyldig sorteringskolonne i PUID-oversikten')
    if column < 8:
        return sorted_puid_groups(rows, column=column, descending=descending,
                                  checked=checked, assessments=assessments)
    labels = policy_labels or {}
    decisions = assessments or {}

    def sort_key(item: Mapping[str, Any]):
        puid = str(item.get('puid') or '')
        value = (format_rule_label(labels.get(puid)) if column == 8
                 else professional_label(decisions.get(puid, '')))
        return _natural(value), _natural(puid)

    # A column-specific projection must not alter the source dictionaries.
    return tuple(dict(row) for row in sorted(rows, key=sort_key,
                                            reverse=bool(descending)))


def next_a9_sort(current: tuple[int, bool], column: int) -> tuple[int, bool]:
    """First click ascends; a repeated click reverses the same column."""
    if type(column) is not int or not 0 <= column < len(MAIN_COLUMNS_A9):
        raise ValueError('Ugyldig sorteringskolonne i PUID-oversikten')
    return column, (not current[1] if current[0] == column else False)


def compact_preference(raw: Any) -> bool:
    """Parse QSettings values conservatively; avoid bool('false') == True."""
    if isinstance(raw, bool):
        return raw
    return str(raw or '').strip().casefold() in {'1', 'true', 'yes', 'on'}
