"""v0.1.10-a3-fix3: ensure light rows and tab selections remain readable.

Pure Python tests, no Qt application or Windows UI required.
"""
from __future__ import annotations

import unittest
from gui_qt.appearance_v0110_a3 import (
    DARK_STYLE, LIGHT_STYLE, _accent_colors, stylesheet_for,
)


def _channels(color: str) -> list[float]:
    value = color.lstrip('#')
    assert len(value) == 6
    return [int(value[n:n + 2], 16) / 255 for n in (0, 2, 4)]


def _luminance(color: str) -> float:
    def f(n):
        return n / 12.92 if n <= 0.04045 else ((n + 0.055) / 1.055) ** 2.4
    return sum(weight * f(n) for weight, n in zip((0.2126, 0.7152, 0.0722), _channels(color)))


def _contrast(a: str, b: str) -> float:
    x, y = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


class LightThemeContrastTests(unittest.TestCase):
    def test_luminance_distinguishes_surfaces(self):
        css = stylesheet_for({'appearance_mode': 'light'})
        self.assertIn('QMainWindow { background-color: #e8edf3;', css)
        self.assertIn('QWidget { background-color: #f3f6fb;', css)
        self.assertIn('QDockWidget { background-color: #f8fafc;', css)
        self.assertIn('background-color: #d7e1ed;', css)
        self.assertIn('alternate-background-color: #e9eff6;', css)
        self.assertIn('QLabel#subtle { color: #475d75; }', css)
        self.assertGreaterEqual(_contrast('#243247', '#f3f6fb'), 9.0)
        self.assertGreaterEqual(_contrast('#475d75', '#f8fafc'), 5.0)

    def test_all_selected_accent_colors_have_readable_white_text(self):
        for accent in ('system', 'blue', 'green', 'purple', 'slate'):
            with self.subTest(accent=accent):
                selected, tab, hover = _accent_colors('light', accent)
                self.assertGreaterEqual(_contrast(selected, '#ffffff'), 4.5)
                self.assertGreaterEqual(_contrast(tab, '#ffffff'), 4.5)
                css = stylesheet_for({'appearance_mode': 'light', 'qt_accent_color': accent})
                self.assertIn('selection-background-color: ' + selected, css)
                self.assertIn('background-color: ' + selected + '; color: #ffffff;', css)
                self.assertIn('QTabBar::tab:selected { background: ' + tab + '; color: #ffffff;', css)
                self.assertIn('QTreeWidget::item:selected', css)
                self.assertIn('QTableWidget::item:selected', css)
                self.assertIn('QTreeView::item:selected', css)
                self.assertIn('QListWidget::item:selected', css)

    def test_dark_and_windows_palettes_are_not_redefined(self):
        self.assertEqual(stylesheet_for({'appearance_mode': 'system'}), '')
        self.assertTrue(stylesheet_for({'appearance_mode': 'dark'}).startswith(DARK_STYLE))
        self.assertNotIn('#e8edf3', DARK_STYLE)
        self.assertNotIn('#10141c', LIGHT_STYLE)

    def test_light_selection_never_uses_pastel_background_with_white_text(self):
        css = stylesheet_for({'appearance_mode': 'light', 'qt_accent_color': 'purple'})
        self.assertIn('selection-background-color: #664898;', css)
        self.assertIn('selection-color: #ffffff;', css)
        self.assertIn('#dcccf4', css)  # pastel is only for hover state
        self.assertNotIn('selection-background-color: #dcccf4', css)
        self.assertNotIn('selection-background-color: #b7d8f7', css)

    def test_light_preview_matches_muted_palette(self):
        from pathlib import Path
        preview_source = (Path(__file__).resolve().parents[1] / 'gui_qt' /
                          'setup_v0110_a3.py').read_text(encoding='utf-8')
        self.assertIn("'Dempet lyst arbeidsområde', '#e8edf3', '#243247'", preview_source)


if __name__ == '__main__':
    unittest.main()
