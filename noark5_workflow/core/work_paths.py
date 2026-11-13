from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Mapping


# Transient context for a Basic job which has already been explicitly marked
# as direct-Work in the shared job model, but whose job.json is not yet on disk.
# Thread/context-local, not a global or persistent override of Setup rules.
_direct_work_context: ContextVar[Path | None] = ContextVar(
    'dwm_selected_direct_work', default=None
)


@contextmanager
def selected_direct_work(work_operations: str | Path):
    """Use a verified Basic direct-Work root while creating its first metadata.

    Callers MUST verify the persisted in-memory __dwm_work_layout__ marker
    before entering. This context only changes path resolution for the named
    directory within the current execution context.
    """
    root = Path(work_operations).resolve(strict=False)
    token = _direct_work_context.set(root)
    try:
        yield
    finally:
        _direct_work_context.reset(token)


def _settings(settings: Mapping[str, object] | None = None) -> Mapping[str, object]:
    if settings is not None:
        return settings
    try:
        from settings import load_config
        return load_config()
    except Exception:
        return {'app_work_subfolder': 'dwm'}


def _is_selected_direct_work(root: Path) -> bool:
    """Check a persisted job marker or a scoped, verified in-memory marker."""
    selected = _direct_work_context.get()
    if selected is not None and root.resolve(strict=False) == selected:
        return True
    marker_file = root / 'job.json'
    try:
        if marker_file.is_symlink() or not marker_file.is_file():
            return False
        size = marker_file.stat().st_size
        if size <= 0 or size > 2_000_000:
            return False
        data = json.loads(marker_file.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict) or data.get('file_type') != 'dwm-work-job':
            return False
        job = data.get('job')
        if not isinstance(job, dict):
            return False
        params = job.get('operation_params')
        if not isinstance(params, dict):
            return False
        layout = params.get('__dwm_work_layout__')
        return isinstance(layout, dict) and layout.get('mode') == 'selected'
    except (OSError, ValueError, UnicodeError, TypeError):
        return False


def resolve_dwm_work_root(
    work_operations: str | Path,
    *,
    settings: Mapping[str, object] | None = None,
) -> Path:
    """Return the authoritative Work root, preserving direct Basic selection."""
    root = Path(work_operations)
    cfg = _settings(settings)
    subfolder = str(cfg.get('app_work_subfolder', 'dwm') or '').strip()
    if not subfolder:
        return root
    subpath = Path(subfolder)
    if subpath.is_absolute():
        raise ValueError('App-undermappe i Work må være relativ.')
    if len(subpath.parts) == 1:
        app_name = subpath.name.casefold()
        if root.name.casefold() == app_name:
            return root
        if root.parent.name.casefold() == app_name:
            return root
    if _is_selected_direct_work(root):
        return root
    return root / subpath


def resolve_work_operations_base(
    work_operations: str | Path,
    *,
    settings: Mapping[str, object] | None = None,
) -> Path:
    root = Path(work_operations)
    cfg = _settings(settings)
    subfolder = str(cfg.get('app_work_subfolder', 'dwm') or '').strip()
    if not subfolder or _is_selected_direct_work(root):
        return root
    subpath = Path(subfolder)
    if subpath.is_absolute():
        raise ValueError('App-undermappe i Work må være relativ.')
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
