"""Presentation-only sorting for A8 PUID groups; never sorts individual Source files.

Groups are small relative to file counts and may be globally sorted before
paging. Each sort is stable and deterministic for the selected scope/filter.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any


LEFT_COLUMNS = ('Velg', 'PUID', 'Kat.', 'MIME', 'Filer')
MAIN_COLUMNS = ('Velg', 'PUID', 'Kategori', 'MIME-gruppe', 'Filformat',
                'Filer', 'Kopier', 'Eksporter', 'Faglig vurdering')
NUMERIC_MAIN_COLUMNS = {5: 'files', 6: 'copy_events', 7: 'copy_exports'}


def _natural(value: Any) -> tuple[tuple[int, Any], ...]:
    """Natural sort: fmt/9 precedes fmt/17; invalid/unidentified stay strings."""
    return tuple((1, int(chunk)) if chunk.isdigit() else (0, chunk.casefold())
                 for chunk in re.split(r'(\d+)', str(value or '')) if chunk)


def sorted_puid_groups(rows: Iterable[Mapping[str, Any]], *,
                       column: int, descending: bool = False,
                       selector: bool = False,
                       checked: Mapping[str, bool] | None = None,
                       assessments: Mapping[str, str] | None = None) -> tuple[dict[str, Any], ...]:
    """Sort all PUID groups, not just one displayed page.

    Check status and assessment are a user-visible projection, never rules
    for approving or changing identified formats.
    """
    limit = len(LEFT_COLUMNS if selector else MAIN_COLUMNS)
    if type(column) is not int or not 0 <= column < limit:
        raise ValueError('Ugyldig sorteringskolonne')
    checked = checked or {}
    assessments = assessments or {}
    groups = [dict(x) for x in rows]

    def key(row: dict[str, Any]):
        puid = str(row.get('puid') or '')
        index = column
        if selector:
            if index == 0:
                primary = int(bool(checked.get(puid, True)))
            elif index == 1:
                primary = _natural(puid)
            elif index == 2:
                primary = _natural(row.get('group'))
            elif index == 3:
                primary = _natural(row.get('mime'))
            else:
                primary = int(row.get('files') or 0)
        else:
            if index == 0:
                primary = int(bool(checked.get(puid, True)))
            elif index == 1:
                primary = _natural(puid)
            elif index == 2:
                primary = _natural(row.get('group'))
            elif index == 3:
                primary = _natural(row.get('mime'))
            elif index == 4:
                primary = _natural(row.get('format'))
            elif index in NUMERIC_MAIN_COLUMNS:
                primary = int(row.get(NUMERIC_MAIN_COLUMNS[index]) or 0)
            else:
                primary = _natural(assessments.get(puid, ''))
        return (primary, _natural(puid))

    return tuple(sorted(groups, key=key, reverse=bool(descending)))


def next_sort(current: tuple[int, bool], column: int,
              *, selector: bool = False) -> tuple[int, bool]:
    """Click a new column for ascending, click the same again for descending."""
    limit = len(LEFT_COLUMNS if selector else MAIN_COLUMNS)
    if type(column) is not int or not 0 <= column < limit:
        raise ValueError('Ugyldig sorteringskolonne')
    return column, not current[1] if current[0] == column else False


def copy_structure(value: Any) -> str:
    """Only the explicit flat alternative overrides the recommended PUID default."""
    return 'flat' if value == 'flat' else 'puid'
