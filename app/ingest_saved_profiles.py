"""Portable, non-sensitive GUI presets for the two-step Ingest dialog.

These are user presets, NOT the externally configured directory-tree profiles.
No receipt number, LABEL, info.xml, extraction ID, password or date is saved.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Mapping

FILE_TYPE = 'dwm-ingest-user-profile'
FORMAT_VERSION = 1
MODE_VALUES = frozenset({'Mottak', 'Uttrekk'})
SAVED_FIELDS = ('setup_file', 'folder_profile_id', 'disk', 'group', 'owner_code', 'default_mode')


def _validate(data: Mapping) -> dict[str, str]:
    if not isinstance(data, Mapping):
        raise ValueError('Mottaksprofil må være et JSON-objekt')
    settings = {key: str(data.get(key, '') or '').strip() for key in SAVED_FIELDS}
    if not settings['setup_file'] or not settings['folder_profile_id']:
        raise ValueError('Profilen må oppgi depot-setup og mappeprofil')
    if settings['default_mode'] not in MODE_VALUES:
        raise ValueError('Ugyldig handling i mottaksprofil')
    owner = settings['owner_code']
    if owner and (len(owner) != 4 or not owner.isdigit()):
        raise ValueError('Eierkommune skal ha fire siffer')
    return settings


def load_ingest_profile(path: str | Path) -> dict[str, str]:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Kunne ikke åpne mottaksprofil: {exc}') from exc
    if not isinstance(data, dict) or data.get('file_type') != FILE_TYPE or data.get('format_version') != FORMAT_VERSION:
        raise ValueError('Ukjent eller ugyldig versjon av mottaksprofil')
    return _validate(data.get('settings', {}))


def save_ingest_profile(path: str | Path, settings: Mapping, *, replace: bool = False) -> Path:
    """Write new profile exclusively, or atomically replace an explicitly opened profile."""
    dest = Path(path)
    config = _validate(settings)
    if dest.suffix.lower() != '.json':
        raise ValueError('Mottaksprofil skal være en .json-fil')
    if not dest.parent.is_dir():
        raise ValueError('Velg en eksisterende mappe for mottaksprofilen')
    if dest.is_symlink():
        raise ValueError('En symbolsk lenke kan ikke brukes som profilfil')
    if dest.exists() and not replace:
        raise FileExistsError(f'Profilen finnes allerede: {dest}')
    content = json.dumps({
        'file_type': FILE_TYPE,
        'format_version': FORMAT_VERSION,
        'settings': config,
    }, ensure_ascii=False, indent=2) + '\n'
    if replace:
        # No original is touched until the replacement is complete and closed.
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                     dir=dest.parent, prefix='.ingest-profile-', suffix='.tmp',
                     delete=False, newline='\n') as handle:
                temp = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, dest)
        finally:
            if temp is not None and temp.exists():
                temp.unlink()
    else:
        with dest.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(content)
    return dest
