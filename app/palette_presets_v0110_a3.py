"""Coordinated Qt surface palettes for DWM v0.1.10-a3.

This module has no Qt dependency; both the GUI and headless tests can reuse
its deterministic colours.  No Source/Work/AIP settings are involved.
"""
from __future__ import annotations

from re import fullmatch
from typing import Mapping

PALETTE_CHOICES: dict[str, str] = {
    'standard': 'Standard – nøytral',
    'ocean': 'Havblå',
    'forest': 'Skoggrønn',
    'lavender': 'Lavendel',
    'rose': 'Rosa',
    'sand': 'Varm sand',
    'custom': 'Egendefinert',
}
CUSTOM_KEYS: dict[str, str] = {
    'window': 'Hovedbakgrunn',
    'surface': 'Paneler og tabeller',
    'button': 'Knapper og verktøylinjer',
    'accent': 'Aktivt valg / markering',
    'text': 'Tekst',
}

# Each preset is a full composition, not just a differently coloured selection.
# The light and dark versions are authored independently for readable contrasts.
ANCHORS = {
    'standard': {
        'light': dict(window='#e8edf3', surface='#f8fafc', button='#dbe5f0', accent='#2f6aa5', text='#243247'),
        'dark': dict(window='#10141c', surface='#151c28', button='#26374b', accent='#315e95', text='#dce5f2'),
    },
    'ocean': {
        'light': dict(window='#e4f0f3', surface='#f3fafb', button='#cee4e9', accent='#205e7e', text='#19394a'),
        'dark': dict(window='#101f2a', surface='#152e3a', button='#214b5a', accent='#256681', text='#e2f1f5'),
    },
    'forest': {
        'light': dict(window='#e7f0e9', surface='#f5faf5', button='#d5e5d8', accent='#1c684b', text='#213c2c'),
        'dark': dict(window='#141e19', surface='#1b2a20', button='#2d4837', accent='#256a4b', text='#e7f4e7'),
    },
    'lavender': {
        'light': dict(window='#eee9f7', surface='#fbf9fe', button='#e0d6f1', accent='#674898', text='#352747'),
        'dark': dict(window='#1e1928', surface='#282137', button='#403454', accent='#72539d', text='#f1e9fa'),
    },
    'rose': {
        'light': dict(window='#f3e5ed', surface='#fff5fa', button='#eed3e1', accent='#ad246a', text='#3d2533'),
        'dark': dict(window='#21141e', surface='#301e2b', button='#4c3043', accent='#b3447c', text='#f6e7f0'),
    },
    'sand': {
        'light': dict(window='#f2ece0', surface='#fcf8f0', button='#e8d9c0', accent='#81551d', text='#3e3221'),
        'dark': dict(window='#252018', surface='#332b20', button='#504130', accent='#91642b', text='#f4e8d2'),
    },
}


def _rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[n:n + 2], 16) for n in (1, 3, 5))


def mix(a: str, b: str, fraction: float) -> str:
    """Interpolate colours without modifying the originals."""
    ca, cb = _rgb(a), _rgb(b)
    return '#' + ''.join(f'{round(x * (1 - fraction) + y * fraction):02x}' for x, y in zip(ca, cb))


def luminance(value: str) -> float:
    channels = [x / 255 for x in _rgb(value)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(x * y for x, y in zip((.2126, .7152, .0722), linear))


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + .05) / (low + .05)


def selected_text(accent: str) -> str:
    return '#ffffff' if contrast(accent, '#ffffff') >= contrast(accent, '#151515') else '#151515'


def normalize_custom_colors(raw: Mapping | None, *, mode: str = 'light') -> dict[str, str]:
    """Validate CSS-safe values and legibility before any settings are saved."""
    if not isinstance(raw, Mapping):
        raise ValueError('Egendefinerte farger må være et objekt med fem farger.')
    if set(raw) != set(CUSTOM_KEYS):
        raise ValueError('Egendefinert palett må ha nøyaktig fem kjente fargefelt.')
    result: dict[str, str] = {}
    for key, label in CUSTOM_KEYS.items():
        value = raw[key]
        if not isinstance(value, str) or not fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError(f'{label} må være en farge på formen #RRGGBB.')
        result[key] = value.lower()
    for surface in ('window', 'surface', 'button'):
        if contrast(result['text'], result[surface]) < 4.5:
            raise ValueError(f'Tekstfargen har for lav kontrast mot {CUSTOM_KEYS[surface].lower()} (minimum 4,5:1).')
    return result


def custom_defaults(mode: str) -> dict[str, str]:
    return dict(ANCHORS['standard']['dark' if mode == 'dark' else 'light'])


def palette_mode(settings: Mapping | None) -> str:
    settings = settings or {}
    raw = str(settings.get('qt_palette_preset') or '').strip().lower()
    if raw in PALETTE_CHOICES:
        return raw
    # A user who chose Rosa in fix4 should receive the complete Rosa scheme.
    if str(settings.get('qt_accent_color') or '').strip().lower() == 'pink':
        return 'rose'
    return 'standard'


def palette_colors(mode: str, preset: str, custom: Mapping | None = None) -> dict[str, str]:
    """Return a coordinated palette for one mode and one named profile."""
    if mode not in ('light', 'dark'):
        raise ValueError('Fargepaletter krever Lys eller Mørk.')
    if preset not in PALETTE_CHOICES:
        raise ValueError('Ukjent fargepalett.')
    if preset == 'custom':
        anchors = normalize_custom_colors(custom, mode=mode)
    else:
        anchors = dict(ANCHORS[preset][mode])
    w, surface, button, accent, text = (anchors[x] for x in CUSTOM_KEYS)
    dark = mode == 'dark'
    neutral = '#ffffff' if dark else '#ffffff'
    widget = mix(w, surface, .52)
    alternate = mix(surface, accent, .09 if not dark else .12)
    header = mix(w, accent, .16 if not dark else .22)
    dock = mix(w, accent, .11 if not dark else .16)
    hover = mix(button, accent, .18 if dark else .17)
    chosen = mix(surface, accent, .20 if not dark else .28)
    input_bg = mix(surface, '#ffffff', .02 if dark else .35)
    border = mix(w, accent, .35 if not dark else .46)
    subdued = mix(text, surface, .26)
    placeholder = mix(text, surface, .35)
    # The selected foreground is computed instead of assuming white on any user
    # colour. For the shipped combinations the selected foreground is white.
    fg = selected_text(accent)
    return {
        'window': w, 'widget': widget, 'surface': surface,
        'alternate': alternate, 'header': header, 'dock': dock,
        'button': button, 'input': input_bg, 'border': border, 'text': text,
        'subtle': subdued, 'placeholder': placeholder, 'accent': accent,
        'tab': accent, 'hover': hover, 'chosen': chosen,
        'selected_text': fg, 'panel': mix(widget, surface, .6),
    }
