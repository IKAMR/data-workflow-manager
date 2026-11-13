"""Non-persistent job-list filename/location suggestions for Basic mode.

Suggestions do not create directories and never change Work or Source. The
shared workbench API remains responsible for saving the actual .n5jobs file.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Mapping


def _safe_stem(value: str) -> str:
    text = str(value or '').translate(str.maketrans({'Æ': 'Ae', 'æ': 'ae', 'Ø': 'Oe', 'ø': 'oe', 'Å': 'Aa', 'å': 'aa', '–': '-', '—': '-'}))
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^A-Za-z0-9._-]+', '_', text)
    return re.sub(r'_+', '_', text).strip('._-')[:96]


def _archive_root(source: Path | None) -> Path | None:
    if source is None:
        return None
    source = Path(source)
    # The typical Noark 5 selected Source is extraction/content/sip/content.
    if (source.name.casefold() == 'content' and source.parent.name.casefold() == 'sip'
            and source.parent.parent.name.casefold() == 'content'):
        return source.parent.parent.parent
    return source


def _operations_root(source: Path | None, work: Path | None) -> Path | None:
    # Prefer the actual Work location, provided it is beneath the named
    # repository_operations directory rather than inferring from another job.
    if work is not None:
        for parent in (Path(work), *Path(work).parents):
            if parent.name.casefold() == 'repository_operations':
                return parent
    if source is None:
        return None
    archive = _archive_root(source)
    # Look at the extraction itself and near ancestors, without crossing into
    # unrelated folders on an arbitrary drive.
    for parent in (archive, archive.parent, archive.parent.parent):
        candidate = parent / 'repository_operations'
        if candidate.is_dir():
            return candidate
    # For an arbitrary selected Source folder, never propose creating a
    # job-list directory *inside* that original Source.
    if archive == Path(source):
        return archive.parent / 'repository_operations'
    return archive / 'repository_operations'


def suggest_joblist_path(*, source: str | Path | None, work: str | Path | None,
                         label: str = '', settings: Mapping | None = None) -> Path | None:
    """Return a proposed path without creating it.

    Setup's job_list_dir wins. Otherwise selected Work/jobblister is used.
    The adjacent repository_operations fallback only applies before Work
    has been selected.
    """
    config = settings or {}
    configured = str(config.get('job_list_dir') or '').strip()
    source_path = Path(source) if source else None
    work_path = Path(work) if work else None
    if configured:
        directory = Path(configured).expanduser()
    elif work_path is not None:
        directory = work_path / 'jobblister'
    else:
        root = _operations_root(source_path, None)
        if root is None:
            return None
        directory = root / 'jobblister'
    archive = _archive_root(source_path)
    identifier = ''
    if archive is not None:
        for segment in (archive.name, *[p.name for p in list(archive.parents)[:3]]):
            found = re.search(r'(?<!\d)(\d{4}[_-]\d{3,4})(?!\d)', segment)
            if found:
                identifier = found.group(1).replace('-', '_')
                break
    label = str(label or '').strip()
    if label.casefold() in ('content', 'sip', 'source', 'ikke angitt'):
        label = ''
    label_stem = _safe_stem(label)
    if identifier and label_stem.casefold().startswith(identifier.casefold()):
        stem = label_stem
    elif identifier and label_stem:
        stem = _safe_stem(identifier + '_' + label_stem)
    else:
        stem = label_stem or identifier or _safe_stem(archive.name if archive else '') or 'ny_kontroll'
    return directory / (stem + '.n5jobs')
