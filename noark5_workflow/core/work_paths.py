from __future__ import annotations

from pathlib import Path
from typing import Mapping


def _settings(settings: Mapping[str, object] | None = None) -> Mapping[str, object]:
    if settings is not None:
        return settings
    try:
        from settings import load_config
        return load_config()
    except Exception:
        return {"app_work_subfolder": "dwm"}


def resolve_dwm_work_root(
    work_operations: str | Path,
    *,
    settings: Mapping[str, object] | None = None,
) -> Path:
    """Return the authoritative root for data owned by DWM.

    ``work_operations`` may be either:
    - the base Work - operations directory, or
    - the already materialized DWM directory, or
    - one job-specific directory directly below the DWM directory.

    The app-owned folder and the job-list output rule are both single
    filesystem components.  Therefore ``.../dwm/a01`` is already inside DWM
    and must never become ``.../dwm/a01/dwm``.
    """
    root = Path(work_operations)
    cfg = _settings(settings)
    subfolder = str(cfg.get("app_work_subfolder", "dwm") or "").strip()
    if not subfolder:
        return root

    subpath = Path(subfolder)
    if subpath.is_absolute():
        raise ValueError("App-undermappe i Work må være relativ.")

    # app_work_subfolder is defined as exactly one component.  Accept both the
    # app root itself (.../dwm) and one materialized job-rule level below it
    # (.../dwm/a01) as already resolved.
    if len(subpath.parts) == 1:
        app_name = subpath.name.casefold()
        if root.name.casefold() == app_name:
            return root
        if root.parent.name.casefold() == app_name:
            return root

    return root / subpath


def resolve_dwm_path(
    work_operations: str | Path,
    *parts: str | Path,
    settings: Mapping[str, object] | None = None,
) -> Path:
    return resolve_dwm_work_root(work_operations, settings=settings).joinpath(*parts)
