"""v0.1.10-a1: data-driven storage-profile choices and Work path proposals.

Profiles map existing Core roles onto physical folders.  A profile selection
never moves files, changes an existing job or silently writes to Source/AIP.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath

from app.job_preflight_v018_a6 import WorkLocationProposal, propose_work_location
from app.storage_layouts import DEFINITION_PATH, materialize_storage_roles, storage_layout_by_id

DEFAULT_STORAGE_PROFILE = 'standard_enkel'
BUILTIN_STORAGE_PROFILE_IDS = (
    'standard_enkel', 'ikamr_standard', 'arkivskaper_hierarkisk',
)
LEGACY_MANUAL_PROFILE_ID = 'none'


@dataclass(frozen=True)
class StorageProfileChoice:
    profile_id: str
    label: str
    description: str
    example_tree: str


def storage_profile_choices(*, include_legacy: bool = False) -> tuple[StorageProfileChoice, ...]:
    """Read display text from the same data file used by the Core role mapper."""
    data = json.loads(DEFINITION_PATH.read_text(encoding='utf-8'))
    definitions = {str(p['id']): p for p in data['profiles']}
    keys = BUILTIN_STORAGE_PROFILE_IDS + ((LEGACY_MANUAL_PROFILE_ID,) if include_legacy else ())
    return tuple(StorageProfileChoice(
        profile_id=key,
        label=str(definitions[key]['label']),
        description=str(definitions[key].get('description', '')),
        example_tree=str(definitions[key].get('example_tree', '')),
    ) for key in keys)


def require_storage_profile(profile_id: str) -> str:
    """Reject unknown choices rather than mapping them silently to 'none'."""
    wanted = str(profile_id or '').strip()
    choices = {p.profile_id for p in storage_profile_choices(include_legacy=True)}
    if wanted not in choices:
        raise ValueError('Ukjent lagringsprofil: ' + (wanted or '(tom)'))
    return wanted


def _operation_suffix(profile_id: str) -> tuple[str, ...]:
    """Resolve relative Work-operation levels from the chosen data profile."""
    template = str(storage_layout_by_id(require_storage_profile(profile_id)).roles.get('work_operations', ''))
    prefix = '{package_root}/'
    if not template.startswith(prefix):
        raise ValueError('Lagringsprofilen har ikke en enkel Work-operasjonssti.')
    remainder = template[len(prefix):]
    components = PurePosixPath(remainder).parts
    if (not components or any(part in ('.', '..') or '{' in part or '}' in part
                              or ':' in part or '\\' in part for part in components)):
        raise ValueError('Ugyldig Work-operasjonssti i lagringsprofilen.')
    return components


def propose_work_with_suffix(
    selected: str | Path, suffix: tuple[str, ...], *, app_subfolder: str = 'dwm',
) -> WorkLocationProposal:
    """Accept an existing Work root, operations folder, DWM folder or job folder.

    Never append duplicate operation levels if the operator selects one of the
    nested folders. Unknown descendants inside the operation folder are rejected.
    """
    chosen = Path(selected)
    if not str(selected).strip() or str(chosen) == '.':
        raise ValueError('Velg en eksisterende Work-mappe.')
    if not suffix or any(not part or part in {'.', '..'} for part in suffix):
        raise ValueError('Ugyldig Work-mappenivaa.')
    components = chosen.parts
    matches = [i for i in range(len(components) - len(suffix) + 1)
               if tuple(part.casefold() for part in components[i:i + len(suffix)]) ==
               tuple(part.casefold() for part in suffix)]
    if matches:
        i = matches[-1]
        work_operations = Path(*components[:i + len(suffix)])
        root = Path(*components[:i])
        remaining = components[i + len(suffix):]
        app = str(app_subfolder or '').strip()
        if not remaining:
            role = 'work_operations'
        elif app and len(remaining) == 1 and remaining[0].casefold() == app.casefold():
            role = 'app_subfolder'
        elif app and len(remaining) == 2 and remaining[0].casefold() == app.casefold():
            role = 'job_subfolder'
        else:
            raise ValueError('Valgt mappe ligger inne i Work-operasjoner, men er ikke '
                             'den definerte DWM-mappen eller en jobbmappe.')
        return WorkLocationProposal(chosen, root, work_operations, role)
    if str(app_subfolder or '').strip().casefold() == chosen.name.casefold():
        raise ValueError('Velg Work-hovedmappen eller den definerte operasjonsmappen, '
                         'ikke en ukjent DWM-mappe.')
    return WorkLocationProposal(
        chosen, chosen, chosen.joinpath(*suffix), 'work_root',
    )


def propose_profile_work_location(
    selected: str | Path, *, profile_id: str = DEFAULT_STORAGE_PROFILE,
    app_subfolder: str = 'dwm',
) -> WorkLocationProposal:
    """Translate a selected root using profile levels without touching disk."""
    profile_id = require_storage_profile(profile_id)
    if profile_id == LEGACY_MANUAL_PROFILE_ID:
        return propose_work_location(selected, app_subfolder=app_subfolder)
    return propose_work_with_suffix(selected, _operation_suffix(profile_id),
                                    app_subfolder=app_subfolder)


def suggest_known_source_work(
    source: str | Path, *, profile_id: str = DEFAULT_STORAGE_PROFILE,
) -> dict[str, Path]:
    """Suggest only when the selected extraction matches the profile's known prefix.

    Unknown source trees produce only source_extraction and must be reviewed
    manually. No directory is created and no AIP target is configured here.
    """
    profile_id = require_storage_profile(profile_id)
    extraction = Path(source)
    return materialize_storage_roles(extraction, layout_id=profile_id)
