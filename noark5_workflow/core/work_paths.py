from __future__ import annotations

import json
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


def _is_selected_direct_work(root: Path) -> bool:
    """Honor Basic's persisted explicit Work layout, without guessing by name.

    The WorkJobStore writes the job definition to root/job.json.  Only this
    precise marker opts a job out of the normal app/job subfolder rules.
    No writes, directory traversal or discovery of neighboring jobs occur.
    """
    marker_file = root / "job.json"
    try:
        if marker_file.is_symlink() or not marker_file.is_file():
            return False
        size = marker_file.stat().st_size
        if size <= 0 or size > 2_000_000:
            return False
        data = json.loads(marker_file.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or data.get("file_type") != "dwm-work-job":
            return False
        job = data.get("job")
        if not isinstance(job, dict):
            return False
        params = job.get("operation_params")
        if not isinstance(params, dict):
            return False
        layout = params.get("__dwm_work_layout__")
        return isinstance(layout, dict) and layout.get("mode") == "selected"
    except (OSError, ValueError, UnicodeError, TypeError):
        return False


def resolve_dwm_work_root(
    work_operations: str | Path,
    *,
    settings: Mapping[str, object] | None = None,
) -> Path:
    """Return the authoritative root for data owned by DWM.

    ``work_operations`` may be either:
    - the base Work - operations directory, or
    - the already materialized DWM directory, or
    - one job-specific directory directly below the DWM directory, or
    - an explicitly selected Basic Work directory containing its job.json.

    The legacy app-owned folder and job-list rule remain unchanged for any
    Work without the persisted direct-selection marker.
    """
    root = Path(work_operations)
    cfg = _settings(settings)
    subfolder = str(cfg.get("app_work_subfolder", "dwm") or "").strip()
    if not subfolder:
        return root

    subpath = Path(subfolder)
    if subpath.is_absolute():
        raise ValueError("App-undermappe i Work må være relativ.")

    if len(subpath.parts) == 1:
        app_name = subpath.name.casefold()
        if root.name.casefold() == app_name:
            return root
        if root.parent.name.casefold() == app_name:
            return root

    # a2.3: check exactly this Work's stored job definition.  The old
    # implementation added /dwm even for an a1.3 direct-Work Basic job,
    # causing Arkade PRONOM evidence to be stored outside Resultatvisninger.
    if _is_selected_direct_work(root):
        return root

    return root / subpath


def resolve_work_operations_base(
    work_operations: str | Path,
    *,
    settings: Mapping[str, object] | None = None,
) -> Path:
    """Return the base Work directory, preserving explicit direct selection."""
    root = Path(work_operations)
    cfg = _settings(settings)
    subfolder = str(cfg.get("app_work_subfolder", "dwm") or "").strip()
    if not subfolder or _is_selected_direct_work(root):
        return root

    subpath = Path(subfolder)
    if subpath.is_absolute():
        raise ValueError("App-undermappe i Work må være relativ.")
    if len(subpath.parts) != 1:
        return root

    app_name = subpath.name.casefold()
    if root.name.casefold() == app_name:
        return root.parent
    if root.parent.name.casefold() == app_name:
        return root.parent.parent
    return root


def resolve_dwm_path(
    work_operations: str | Path,
    *parts: str | Path,
    settings: Mapping[str, object] | None = None,
) -> Path:
    return resolve_dwm_work_root(work_operations, settings=settings).joinpath(*parts)
