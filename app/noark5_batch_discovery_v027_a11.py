"""Safe Noark 5 batch discovery and explicit Work planning (v0.2.7-a11).

No document payload is traversed, moved, written or hashed. This module does
not create jobs, directories or job lists; those are operator-approved GUI actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re

SKIP = frozenset({'dokument', 'dokumenter', 'repository_operations',
                  'external_evidence', '.git', 'wf', 'diagnostics', 'node_modules'})
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True)
class Candidate:
    source: Path
    package_root: Path
    info_xml: Path | None = None


def component(value: str) -> str:
    value = str(value or '').strip()
    if not value or value in ('.', '..') or _BAD.search(value) or value.endswith(('.', ' ')):
        raise ValueError('Bruk ett gyldig mappenavn, f.eks. a01 (uten skråstrek).')
    return value


def package_root_for(source: Path, search_root: Path) -> Path:
    """Recognize established content/sip/content layout without guessing old Work."""
    parts = source.parts
    lowered = [s.casefold() for s in parts]
    for i in range(len(parts) - 3):
        if lowered[i:i+3] == ['content', 'sip', 'content']:
            return Path(*parts[:i])
    # Standard layout when each immediate child of search root is one package.
    relative = source.relative_to(search_root)
    if len(relative.parts) >= 2:
        return search_root / relative.parts[0]
    # Root itself is a candidate: choose its parent as package context.
    return source.parent


def discover(root: str | Path, *, max_directories: int = 100000,
             cancelled=None) -> tuple[Candidate, ...]:
    root = Path(root).resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Hovedmappen må være en eksisterende vanlig mappe.')
    found: list[Candidate] = []
    visited = 0
    for folder, dirs, names in os.walk(root, topdown=True, followlinks=False):
        if cancelled and cancelled():
            raise InterruptedError('Søket er avbrutt.')
        visited += 1
        if visited > max_directories:
            raise ValueError('Søket oversteg kataloggrensen. Velg en mer avgrenset hovedmappe.')
        here = Path(folder)
        has_docs = any(d.casefold() in {'dokument', 'dokumenter'} for d in dirs)
        dirs[:] = sorted((d for d in dirs if d.casefold() not in SKIP
                          and not (here / d).is_symlink()
                          and not (getattr(here / d, 'is_junction', lambda: False)())),
                         key=str.casefold)
        lower_names = {name.casefold() for name in names}
        # The established discovery definition requires both metadata and a
        # document folder; never assume arbitrary directories are Noark 5.
        has_xml = 'arkivstruktur.xml' in lower_names
        if has_xml and has_docs:
            found.append(Candidate(here, package_root_for(here, root)))
    return tuple(sorted(found, key=lambda c: str(c.source).casefold()))


def resolve_info_xml(candidate: Candidate, info_root: str | Path | None = None) -> Path | None:
    """Conservative deterministic match: never assign one package's METS to another."""
    roots: list[Path] = [candidate.source, candidate.source.parent,
                         candidate.package_root, candidate.package_root / 'metadata']
    if info_root:
        base = Path(info_root).resolve(strict=True)
        if not base.is_dir():
            raise ValueError('Valgt info.xml-katalog finnes ikke.')
        # Only exact package/extraction named paths and a direct file for a
        # single-source folder; no fuzzy matches or arbitrary first-file wins.
        roots.extend((base / candidate.package_root.name,
                      base / candidate.source.name))
    matches: list[Path] = []
    for root in roots:
        for filename in ('info.xml', 'INFO.XML', 'Info.xml'):
            path = root / filename
            try:
                if path.is_file() and not path.is_symlink() and path.stat().st_size <= 8_000_000:
                    resolved = path.resolve(strict=True)
                    if resolved not in matches:
                        matches.append(resolved)
            except OSError:
                pass
    if len(matches) > 1:
        return None   # Ambiguity requires manual choice, not guessing.
    return matches[0] if matches else None


def plan_work(candidate: Candidate, *, dwm_folder: str = 'dwm',
              run_folder: str = 'a01') -> Path:
    base = candidate.package_root / 'repository_operations'
    if dwm_folder:
        base /= component(dwm_folder)
    return base / component(run_folder)


def assign_work(candidates: tuple[Candidate, ...], *, dwm_folder: str = 'dwm',
                run_folder: str = 'a01') -> dict[Path, Path]:
    """Keep one Work per Source even if several candidates share package root."""
    plans: dict[Path, Path] = {}
    used: set[str] = set()
    for c in candidates:
        target = plan_work(c, dwm_folder=dwm_folder, run_folder=run_folder)
        key = str(target).casefold()
        if key in used:
            safe = re.sub(r'[^\w.-]', '_', c.source.name).strip('._') or 'uttrekk'
            target = target / safe
            key = str(target).casefold()
        if key in used:
            raise ValueError('Uttrekkene gir samme Work-mappe: ' + str(target))
        used.add(key)
        plans[c.source] = target
    return plans
