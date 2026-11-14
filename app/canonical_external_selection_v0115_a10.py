"""Pure selection helpers for inline Arkade/Siegfried sources in canonical GUI.

Only the previously saved selection can mark an external candidate; discovery
itself never selects arbitrary new sources. No files are changed here.
"""
from __future__ import annotations


def external_row_metadata(candidates: list[dict], previous: list[str]) -> list[dict]:
    previously_selected = set(previous)
    result = []
    seen = set()
    for item in candidates:
        path = item.get('path')
        if not isinstance(path, str) or not path or path.casefold() in seen:
            continue
        seen.add(path.casefold())
        result.append({
            'path': path,
            'label': item.get('label') or 'Eksternt resultat',
            'bytes': item.get('bytes', 0),
            'selected': path in previously_selected,
        })
    return result


def selected_external_rows(rows: list[tuple[str, str, bool]]) -> tuple[str, ...]:
    """Return checked external evidence, never internal DWM master/raw input."""
    return tuple(path for category, path, checked in rows
                 if category == 'external' and checked)
