"""Operator-facing status for one immutable DIAS source and editable metadata.

Only describes existing evidence; never changes Source, Work or the job model.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence


def _normalized(values: Mapping | None) -> dict[str, str]:
    return {str(k): str(v or '').strip() for k, v in (values or {}).items()}


def _different(current: Mapping | None, baseline: Mapping | None) -> bool:
    values = _normalized(current)
    original = _normalized(baseline)
    # Current contains canonical DIAS keys. Source imports may also include
    # legacy aliases, which must not create artificial differences.
    return any(value != original.get(key, '') for key, value in values.items())


def describe_info_xml_status(
    current: Mapping | None,
    source_imports: Sequence[Mapping] = (),
    *,
    original: str | Path | None = None,
    original_fields: Mapping | None = None,
    dirty: bool = False,
) -> str:
    """Distinguish imported/unchanged, edited, generated and not found.

    A discovered but unimported Source file is never falsely called imported.
    Pending values are marked when they are not yet saved to Work.
    """
    imports = [item for item in source_imports if isinstance(item, Mapping)]
    if imports:
        baseline = imports[-1].get('fields') or {}
        if _different(current, baseline):
            return 'Redigert (ikke lagret)' if dirty else 'Redigert'
        return 'Original importert'
    path_exists = False
    if original:
        try:
            path_exists = Path(original).is_file()
        except (OSError, ValueError, TypeError):
            pass
    if path_exists:
        if dirty and original_fields and _different(current, original_fields):
            return 'Redigert (ikke lagret)'
        return 'Funnet – ikke importert'
    if any(_normalized(current).values()):
        return 'Opprettet i DWM (ikke lagret)' if dirty else 'Opprettet i DWM'
    return 'Ikke funnet'
