"""Validated DWM UI navigation preferences (no GUI toolkit dependency).

These keys govern only GUI presentation and startup navigation, never job
execution, operation maturity, Source/Work layout or DIAS preservation.
"""
from __future__ import annotations

from typing import Mapping

UI_SETUP_KEYS = frozenset({
    'ui_work_profile', 'ui_startup_mode', 'ui_visible_sections',
    'ui_startup_page', 'ui_area_visibility',
})
WORK_PROFILES = ('control', 'depot', 'custom')
START_MODES = ('last', 'basic', 'advanced')
# 'profile' retains a2 behaviour: Control profile opens Control; depot/custom
# opens Home. 'last' instead restores the actual last navigation page.
START_PAGES = ('profile', 'last', 'home', 'control')
WORK_SECTIONS = ('ingest', 'antivirus', 'workspace', 'control', 'report', 'preserve', 'crm', 'access')
# Same 0/1/2 maturity scale as app.operation_metadata (alpha/beta/stable).
# Separate threshold because work-area navigation and operation selection are
# independent concerns. Zero preserves a2's eight-card depot landing page.
WORK_AREA_VISIBILITY_LABELS = {
    0: '0 – Alle (inkl. Alpha)',
    1: '1 – Beta og stabile',
    2: '2 – Kun stabile',
}
UI_DEFAULTS = {
    'ui_work_profile': 'control',
    'ui_startup_mode': 'basic',
    'ui_visible_sections': ['control'],
    'ui_startup_page': 'profile',
    'ui_area_visibility': 0,
}


def validate_ui_preferences(changes: Mapping[str, object]) -> dict[str, object]:
    """Validate updates before the existing shared Setup API can persist them."""
    unknown = set(changes) - UI_SETUP_KEYS
    if unknown:
        raise ValueError('Ukjente GUI-innstillinger: ' + ', '.join(sorted(unknown)))
    result: dict[str, object] = {}
    if 'ui_work_profile' in changes:
        value = changes['ui_work_profile']
        if not isinstance(value, str) or value not in WORK_PROFILES:
            raise ValueError('Ukjent arbeidsprofil.')
        result['ui_work_profile'] = value
    if 'ui_startup_mode' in changes:
        value = changes['ui_startup_mode']
        if not isinstance(value, str) or value not in START_MODES:
            raise ValueError('Ukjent oppstartsmodus for Kontroll.')
        result['ui_startup_mode'] = value
    if 'ui_startup_page' in changes:
        value = changes['ui_startup_page']
        if not isinstance(value, str) or value not in START_PAGES:
            raise ValueError('Ukjent oppstartsside.')
        result['ui_startup_page'] = value
    if 'ui_area_visibility' in changes:
        value = changes['ui_area_visibility']
        if type(value) is not int or value not in WORK_AREA_VISIBILITY_LABELS:
            raise ValueError('Synlige arbeidsområder må velges som 0, 1 eller 2.')
        result['ui_area_visibility'] = value
    if 'ui_visible_sections' in changes:
        value = changes['ui_visible_sections']
        if not isinstance(value, (tuple, list)) or any(
            not isinstance(item, str) or item not in WORK_SECTIONS for item in value
        ):
            raise ValueError('Ugyldig liste over synlige arbeidsområder.')
        result['ui_visible_sections'] = list(dict.fromkeys(value))
    return result
