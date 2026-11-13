"""Read-only bridge from legacy DWM job-list history to the Qt workbench.

No directory search, config write or job-file mutation. Qt's own recent files
are retained separately from legacy settings to avoid changing legacy behavior.

The last explicitly selected job list is an *intent*, not a discovered file.
An encrypted or disconnected drive must not cause a different recent job to
become the active job silently at startup.
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
    """Return recent lists with a non-fallback first slot for the last choice.

    With ``existing_only=True`` other historical entries are filtered as
    before. The *explicit last choice* remains present even when temporarily
    unavailable, so startup attempts it (and shows the existing open-error
    dialog) instead of silently loading another job's data. This does not
    claim the file exists; callers still have to validate it before use.
    """
    legacy = legacy_settings or {}
    qt_last_values = _strings(qt_last)
    legacy_last_values = _strings(legacy.get("last_job_list_file"))
    explicitly_last = qt_last_values or legacy_last_values
    candidates = (
        qt_last_values
        + (legacy_last_values if not qt_last_values else ())
        + _strings(qt_recent)
        + (legacy_last_values if qt_last_values else ())
        + _strings(legacy.get("recent_job_list_files"))
    )
    protected_identity = None
    if explicitly_last:
        protected = Path(explicitly_last[0]).expanduser()
        if protected.suffix.casefold() == ".n5jobs":
            protected_identity = _identity(str(protected))

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
        if existing_only and key != protected_identity and not path.is_file():
            continue
        selected.append(str(path))
        if len(selected) >= max(1, int(limit)):
            break
    return tuple(selected)


def remember_joblist(path: str | Path, previous: object, *, limit: int = MAX_RECENT) -> tuple[str, ...]:
    """Return updated Qt-only MRU without writing to source/legacy config."""
    return recent_joblists(path, previous, existing_only=False, limit=limit)
