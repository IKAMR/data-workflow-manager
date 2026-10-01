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

    External tools use ``work_operations`` directly and manage their own output
    folders. DWM-owned files always live below ``app_work_subfolder`` when that
    setting is non-blank. A blank setting deliberately means the Work -
    operations root itself.

    The function is idempotent for callers that already pass the resolved DWM
    root.
    """
    root = Path(work_operations)
    cfg = _settings(settings)
    subfolder = str(cfg.get("app_work_subfolder", "dwm") or "").strip()
    if not subfolder:
        return root

    subpath = Path(subfolder)
    if subpath.is_absolute():
        raise ValueError("App-undermappe i Work må være relativ.")

    # Preserve the existing setting semantics while avoiding accidental
    # ``.../dwm/dwm`` when an already-resolved root is passed internally.
    if len(subpath.parts) == 1 and root.name.casefold() == subpath.name.casefold():
        return root
    return root / subpath


def resolve_dwm_path(
    work_operations: str | Path,
    *parts: str | Path,
    settings: Mapping[str, object] | None = None,
) -> Path:
    return resolve_dwm_work_root(work_operations, settings=settings).joinpath(*parts)
