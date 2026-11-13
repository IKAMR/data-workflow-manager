"""Read-only inspection of a proposed Basic Work directory.

No directory is created and no file is modified by this module.  A directory
containing unidentified DWM material is never approved for a *new* job.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

def nearby_job_lists(path: str | Path, *, limit: int = 30) -> tuple[Path, ...]:
    """Find local job-list candidates for a user to inspect; do not trust them.

    Reading a candidate does not approve Work or establish job identity.
    The shared workbench API validates a job list when it is opened.
    """
    root = Path(path).resolve(strict=False)
    candidates: list[Path] = []
    for folder in (root, root.parent, root.parent.parent):
        if not folder.is_dir():
            continue
        try:
            for item in folder.iterdir():
                if item.is_file() and item.suffix.casefold() == ".n5jobs":
                    candidates.append(item)
                    if len(candidates) >= limit:
                        return tuple(candidates)
        except OSError:
            continue
    return tuple(candidates)


DWM_MARKERS = frozenset({
    'job.json', 'depot_metadata.json', 'run.json', 'run_state.json',
    'external_evidence', 'noark5_tests', 'wf', 'metadata', 'runs',
    'logs', 'reports', 'arkade5', 'siegfried', 'dwm',
})


def _same(a: str | Path, b: str | Path) -> bool:
    x = os.path.normcase(str(Path(a).resolve(strict=False)))
    y = os.path.normcase(str(Path(b).resolve(strict=False)))
    return x.casefold() == y.casefold()


def _job_source(path: Path) -> str | None:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict):
        return None
    for node in (value.get('job'), value):
        if not isinstance(node, dict):
            continue
        for key in ('source_extraction', 'source_root', 'archive_root'):
            if node.get(key):
                return str(node[key])
    return None


@dataclass(frozen=True)
class WorkInspection:
    path: Path
    kind: str  # empty, unrelated, same_job, different_source, unknown_job
    entries: tuple[str, ...]
    count: int
    recorded_source: str = ''

    def summary(self) -> str:
        names = '\n'.join('  - ' + x for x in self.entries)
        if self.count > len(self.entries):
            names += f'\n  ... og {self.count - len(self.entries)} til'
        return ('Work: ' + str(self.path) + '\n'
                + ('Registrert Source: ' + self.recorded_source + '\n' if self.recorded_source else '')
                + f'Elementer på toppnivå: {self.count}\n' + (names or '  (tom)'))


def work_contains_only_joblists(root: str | Path) -> bool:
    """True only for Work holding a bounded jobblister directory with .n5jobs.

    A saved list is not a Work job, and must not block a new run. Never
    mistake arbitrary content or a DWM artifact for an empty Work directory.
    """
    root = Path(root)
    try:
        entries = list(root.iterdir())
        if len(entries) != 1:
            return False
        folder = entries[0]
        if (folder.is_symlink() or not folder.is_dir()
                or folder.name.casefold() != 'jobblister'):
            return False
        for index, item in enumerate(folder.iterdir()):
            if (index >= 256 or item.is_symlink() or not item.is_file()
                    or item.suffix.casefold() != '.n5jobs'):
                return False
        return True
    except OSError:
        return False


def inspect_work(path: str | Path, source: str | Path, *, max_entries: int = 4000) -> WorkInspection:
    root = Path(path).resolve(strict=False)
    if not root.exists():
        return WorkInspection(root, 'empty', (), 0)
    if not root.is_dir():
        raise ValueError('Work må være en mappe.')
    entries = []
    markers = False
    job_files = []
    count = 0
    try:
        for child in root.iterdir():
            count += 1
            if count > max_entries:
                raise ValueError('For mange elementer i Work til sikker vurdering.')
            if len(entries) < 14:
                entries.append(child.name + ('/' if child.is_dir() else ''))
            if child.name.casefold() in DWM_MARKERS or child.name.casefold().endswith('.n5jobs'):
                markers = True
            if child.name.casefold() == 'job.json':
                job_files.append(child)
            # Scan a limited, known DWM nesting without recursive whole-disk walks.
            if child.is_dir() and child.name.casefold() in ('dwm', 'metadata', 'wf'):
                for nested in child.glob('*/job.json'):
                    job_files.append(nested)
        if not count:
            return WorkInspection(root, 'empty', (), 0)
        if work_contains_only_joblists(root):
            return WorkInspection(root, 'empty', tuple(entries), count)
    except OSError as exc:
        raise ValueError('Kan ikke kontrollere Work-innhold: ' + str(exc)) from exc
    recorded = [_job_source(f) for f in job_files]
    recorded = [v for v in recorded if v]
    if recorded:
        kind = 'same_job' if all(_same(v, source) for v in recorded) else 'different_source'
        return WorkInspection(root, kind, tuple(entries), count, ', '.join(sorted(set(recorded))))
    return WorkInspection(root, 'unknown_job' if markers else 'unrelated', tuple(entries), count)
