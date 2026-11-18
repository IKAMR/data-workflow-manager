"""Bounded, read-only Source candidates based on a manually imported info.xml.

Never silently select the last extraction or match an unrelated sibling.
This module never writes files, walks document payload trees, or imports Qt.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Callable

# Skip folders that can contain millions of documents, Work data or generated reports.
SKIP_SUBTREES = frozenset({
    'dokumenter', 'documents', 'document', 'work', 'aip', 'repository_operations',
    'dwm', '.git', 'logs', 'log', 'reports', 'resultater',
})
MARKERS = ('arkivstruktur.xml',)


def is_info_xml(path: str | Path) -> bool:
    name = Path(path).name.casefold()
    return name == 'info.xml' or name.endswith('_info.xml')


MAX_DEPTH = 5
MAX_DIRECTORIES = 240


def find_source_candidates(info_xml: str | Path, *, validator: Callable[[Path], bool] | None = None,
                           max_depth: int = MAX_DEPTH,
                           max_directories: int = MAX_DIRECTORIES) -> tuple[Path, ...]:
    """Find potential Noark5 Source roots strictly AT/BELOW info.xml's parent.

    A validator may enforce additional extraction checks. Exceeding search limits
    results in partial candidates, never widening scope or auto-selection.
    """
    path = Path(info_xml)
    if not is_info_xml(path) or not path.is_file():
        return ()
    root = path.parent
    queue = deque([(root, 0)])
    visited = set()
    matches = []
    maximum = max(1, min(int(max_directories), 1000))
    depth_limit = max(0, min(int(max_depth), 8))
    while queue and len(visited) < maximum:
        directory, depth = queue.popleft()
        try:
            resolved = directory.resolve(strict=False)
            if resolved in visited or directory.is_symlink():
                continue
            visited.add(resolved)
            if any((directory / marker).is_file() for marker in MARKERS):
                if validator is None or validator(directory):
                    matches.append(directory)
                continue
            if depth >= depth_limit:
                continue
            # Keep network and multi-TB scans bounded. Never follow symlinks.
            children = []
            for child in directory.iterdir():
                if len(children) >= 200:
                    break
                if child.name.casefold() in SKIP_SUBTREES or child.is_symlink():
                    continue
                if child.is_dir():
                    children.append(child)
            children.sort(key=lambda p: (p.name.casefold() not in ('content','sip','uttrekk'),
                                          p.name.casefold()))
            queue.extend((child, depth + 1) for child in children)
        except (OSError, PermissionError):
            continue
    return tuple(matches)


def source_within_info_parent(source: str | Path, info_xml: str | Path) -> bool:
    """Geographic proximity check only, NOT an assertion of archive identity."""
    parent = Path(info_xml).parent.resolve(strict=False)
    candidate = Path(source).resolve(strict=False)
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True


def picker_start(info_xml: str | Path | None, *, home: str | Path) -> Path:
    """Explicit info.xml context wins; an old job path is never a default."""
    if info_xml is not None:
        info = Path(info_xml)
        if is_info_xml(info) and info.is_file():
            return info.parent
    return Path(home)
