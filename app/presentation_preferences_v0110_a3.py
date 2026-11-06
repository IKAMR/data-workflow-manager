"""v0.1.10-a3: validated display preferences, independent of GUI libraries."""
from __future__ import annotations

from app.palette_presets_v0110_a3 import (
    PALETTE_CHOICES, normalize_custom_colors,
)

DISPLAY_KEYS = frozenset({
    'appearance_mode', 'qt_accent_color', 'qt_popup_placement',
    'qt_palette_preset', 'qt_custom_colors',
})
VALID_VALUES = {
    'appearance_mode': frozenset({'system', 'dark', 'light'}),
    'qt_accent_color': frozenset({'system', 'blue', 'green', 'purple', 'pink', 'slate'}),
    'qt_popup_placement': frozenset({'auto', 'over', 'beside'}),
    'qt_palette_preset': frozenset(PALETTE_CHOICES),
}


def validate_display_preferences(changes) -> dict[str, object]:
    """Reject unknown and unsafe styles before writing settings.

    Custom colours are stored as a JSON object and never converted to a Python
    repr string.  This method performs no writes, GUI calls or side effects.
    """
    validated: dict[str, object] = {}
    for key in DISPLAY_KEYS.intersection(changes):
        if key == 'qt_custom_colors':
            # Validating both light and dark surface contrast prevents unreadable
            # choices after the user later switches base themes.
            validated[key] = normalize_custom_colors(changes[key])
            continue
        value = str(changes[key] or '').strip().lower()
        if value not in VALID_VALUES[key]:
            raise ValueError(f'Ugyldig innstilling {key}: {value!r}')
        validated[key] = value
    if validated.get('qt_palette_preset') == 'custom' and 'qt_custom_colors' not in validated:
        raise ValueError('Egendefinert palett krever fem validerte farger.')
    return validated
