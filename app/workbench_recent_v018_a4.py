"""Read-only bridge from legacy DWM job-list history to the Qt workbench.

No directory search, config write or job-file mutation. Qt's own recent files
are retained separately from legacy settings to avoid changing legacy behavior.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

MAX_RECENT = 12


def _strings(values: object) -> tuple[str, ...]:
    if isinstance(values, (str, Path)):
        values = (values,)
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(value).strip() for value in values if value and str(value).strip())


def _identity(path: str) -> str:
    """Deduplicate Windows paths without normalising/moving actual files."""
    return path.replace("/", "\\").casefold()


def recent_joblists(
    qt_last: str | Path | None,
    qt_recent: object,
    legacy_settings: Mapping[str, object] | None = None,
    *,
    existing_only: bool = True,
    limit: int = MAX_RECENT,
) -> tuple[str, ...]:
    """Merge Qt and legacy history, prioritising Qt, without scanning folders."""
    legacy = legacy_settings or {}
    candidates = (
        _strings(qt_last)
        + _strings(qt_recent)
        + _strings(legacy.get("last_job_list_file"))
        + _strings(legacy.get("recent_job_list_files"))
    )
    selected: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.suffix.casefold() != ".n5jobs":
            continue
        key = _identity(str(path))
        if key in seen:
            continue
        seen.add(key)
        if existing_only and not path.is_file():
            continue
        selected.append(str(path))
        if len(selected) >= max(1, int(limit)):
            break
    return tuple(selected)


def remember_joblist(path: str | Path, previous: object, *, limit: int = MAX_RECENT) -> tuple[str, ...]:
    """Return updated Qt-only MRU without writing to the source/legacy config."""
    return recent_joblists(path, previous, existing_only=False, limit=limit)
