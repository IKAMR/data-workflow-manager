"""a3-fix4: a readable pink accent in existing light/dark modes.

No change to Windows native colours, window placement or stored job paths.
"""
from __future__ import annotations

import unittest

from app.presentation_preferences_v0110_a3 import validate_display_preferences
from gui_qt.appearance_v0110_a3 import (
    ACCENT_CHOICES, _accent_colors, stylesheet_for,
)


def _luminance(hex_color: str) -> float:
    parts = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in parts]
    return sum(a * b for a, b in zip((.2126, .7152, .0722), linear))


def _contrast_with_white(color: str) -> float:
    return 1.05 / (_luminance(color) + .05)


class PinkAccentTests(unittest.TestCase):
    def test_sixth_accent_is_named_pink_in_norwegian(self):
        self.assertEqual(ACCENT_CHOICES['pink'], 'Rosa')
        self.assertEqual(len(ACCENT_CHOICES), 6)
        self.assertEqual(validate_display_preferences({'qt_accent_color': 'pink'}),
                         {'qt_accent_color': 'pink'})

    def test_light_selected_items_and_tabs_pass_wcag_normal_text_contrast(self):
        selected, tab, hover = _accent_colors('light', 'pink')
        self.assertGreaterEqual(_contrast_with_white(selected), 4.5)
        self.assertGreaterEqual(_contrast_with_white(tab), 4.5)
        self.assertNotEqual(selected, hover)
        css = stylesheet_for({'appearance_mode': 'light', 'qt_accent_color': 'pink'})
        self.assertIn(f'selection-background-color: {selected};', css)
        self.assertIn(f'background-color: {selected}; color: #ffffff;', css)
        self.assertIn(f'QTabBar::tab:selected {{ background: {tab}; color: #ffffff;', css)
        self.assertNotIn(f'selection-background-color: {hover};', css)

    def test_dark_pink_is_distinct_and_legible(self):
        selected, tab, hover = _accent_colors('dark', 'pink')
        self.assertGreaterEqual(_contrast_with_white(selected), 4.5)
        self.assertGreaterEqual(_contrast_with_white(tab), 4.5)
        css = stylesheet_for({'appearance_mode': 'dark', 'qt_accent_color': 'pink'})
        self.assertIn(selected, css)
        self.assertIn(tab, css)
        self.assertIn(hover, css)
        self.assertNotEqual(css, stylesheet_for({'appearance_mode': 'dark', 'qt_accent_color': 'purple'}))

    def test_native_windows_and_existing_purple_not_modified(self):
        self.assertEqual(stylesheet_for({'appearance_mode': 'system', 'qt_accent_color': 'pink'}), '')
        self.assertEqual(_accent_colors('dark', 'purple'), ('#7b5ab3', '#684a9e', '#625081'))
        self.assertEqual(_accent_colors('light', 'purple'), ('#664898', '#6d4b9f', '#dcccf4'))

    def test_setup_has_selection_outline_for_pink(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'gui_qt' / 'setup_v0110_a3.py').read_text('utf-8')
        self.assertIn("'pink': '#b3447c'", source)
        self.assertIn('for key, label in ACCENT_CHOICES.items():', source)
        self.assertIn('self.accent_combo.addItem(label, key)', source)
        self.assertNotIn('save_config(', source)

if __name__ == '__main__':
    unittest.main()
