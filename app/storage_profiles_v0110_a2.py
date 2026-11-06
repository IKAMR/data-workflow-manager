"""v0.1.10-a2: safe, non-persistent resolution of default storage profile.

In v0.1.9 the global default was ``ikamr_standard``. Older config.json files
therefore contain this value even where the operator never selected a storage
profile. A2 treats that *unmarked legacy default* as 'Standard – enkel'.

The first explicit Save in a2 marks the chosen profile, which is then kept on
subsequent launches. No job, Work manifest or source folder is modified here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Any

DEFAULT_STORAGE_PROFILE = 'standard_enkel'
LEGACY_UNSELECTED_DEFAULTS = frozenset({'ikamr_standard', 'none'})
_PROFILE_FILE = Path(__file__).resolve().parents[1] / 'config' / 'storage_layouts.json'


def _profiles() -> dict[str, dict]:
    raw = json.loads(_PROFILE_FILE.read_text(encoding='utf-8'))
    return {str(item['id']): item for item in raw['profiles']}


def resolve_storage_profile(settings: Mapping[str, Any] | None) -> str:
    """Return the effective new-job profile without changing saved settings.

    Never override a profile explicitly saved by a2. Preserve a1-only
    non-legacy profile selections as they could only have been actively chosen.
    A legacy unmarked IKAMR default is not proof of user selection.
    """
    values = settings or {}
    selected = str(values.get('storage_layout_profile') or '').strip()
    if not selected or selected not in _profiles():
        return DEFAULT_STORAGE_PROFILE
    explicitly_selected = values.get('storage_layout_profile_selected') is True
    if not explicitly_selected and selected in LEGACY_UNSELECTED_DEFAULTS:
        return DEFAULT_STORAGE_PROFILE
    return selected


def profile_best_for(profile_id: str) -> str:
    """Human-readable, data-driven explanation for the visible Setup card."""
    return str(_profiles().get(profile_id, {}).get('best_for', '')).strip()
