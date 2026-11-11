"""Read-only discovery of an existing Siegfried install, shared with SIARD WM.

No auto-install, subprocess launch, download, PATH changes, or writes. DWM can
later use the discovered executable in its own provenance-aware operation.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _shared_root(environ: dict[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    if sys.platform == 'win32':
        return Path(env.get('LOCALAPPDATA', str(Path.home()))) / 'SIARDManager' / 'siegfried'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'SIARDManager' / 'siegfried'
    return Path(env.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'SIARDManager' / 'siegfried'


def find_siegfried_executable(configured: str = '', *,
                              shared_root: Path | None = None,
                              include_path: bool = True) -> Path | None:
    """Search only a configured file, known shared directory and normal PATH.

    SIARD may extract the official ZIP into one subdirectory; inspect one level
    of children only. Never recursively search a user's archive or Work drive.
    """
    binary = 'sf.exe' if sys.platform == 'win32' else 'sf'
    if configured:
        path = Path(configured.strip().strip('"')).expanduser()
        if path.is_file() and path.name.casefold() == binary.casefold():
            return path.resolve(strict=True)
    root = Path(shared_root) if shared_root is not None else _shared_root()
    candidates = [root / binary]
    try:
        if root.is_dir():
            for child in list(root.iterdir())[:120]:
                if child.is_dir() and not child.is_symlink():
                    candidates.append(child / binary)
    except OSError:
        pass
    for path in candidates:
        try:
            if path.is_file():
                return path.resolve(strict=True)
        except (OSError, RuntimeError):
            pass
    if include_path:
        found = shutil.which(binary) or shutil.which('sf')
        if found and Path(found).is_file():
            return Path(found).resolve(strict=True)
    return None
