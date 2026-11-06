"""a3-fix5: whole-window schemes and safe, editable user palettes.

Headless: verifies real theme generation, persistence validation and the dialog
code contracts without requiring a Qt desktop or opening any user data.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.palette_presets_v0110_a3 import (
    PALETTE_CHOICES, CUSTOM_KEYS, ANCHORS, contrast, custom_defaults,
    normalize_custom_colors, palette_colors, palette_mode, selected_text,
)
from app.presentation_preferences_v0110_a3 import validate_display_preferences
from gui_qt.appearance_v0110_a3 import stylesheet_for, active_palette, DARK_STYLE, LIGHT_STYLE
from settings import DEFAULT_CONFIG, load_config, save_config

ROOT = Path(__file__).resolve().parents[1]
SETUP = (ROOT / 'gui_qt' / 'setup_v0110_a3.py').read_text(encoding='utf-8')
API = (ROOT / 'app' / 'workbench_api_v0110_a1.py').read_text(encoding='utf-8')


class FullPaletteTests(unittest.TestCase):
    def test_standard_plus_five_named_palettes_and_custom(self):
        self.assertEqual(tuple(PALETTE_CHOICES),
                         ('standard', 'ocean', 'forest', 'lavender', 'rose', 'sand', 'custom'))
        self.assertEqual(PALETTE_CHOICES['rose'], 'Rosa')
        self.assertEqual(palette_mode({}), 'standard')
        self.assertEqual(palette_mode(DEFAULT_CONFIG), 'standard')
        self.assertEqual(palette_mode({'qt_accent_color': 'pink'}), 'rose')
        self.assertEqual(palette_mode({**DEFAULT_CONFIG, 'qt_accent_color': 'pink'}), 'rose')
        self.assertEqual(palette_mode({'qt_palette_preset': 'forest', 'qt_accent_color': 'pink'}), 'forest')

    def test_each_preset_changes_surface_controls_header_and_selection(self):
        for name in ('ocean', 'forest', 'lavender', 'rose', 'sand'):
            for mode in ('light', 'dark'):
                with self.subTest(name=name, mode=mode):
                    c = palette_colors(mode, name)
                    css = stylesheet_for({'appearance_mode': mode, 'qt_palette_preset': name})
                    self.assertIn(f'QMainWindow {{ background-color: {c["window"]}', css)
                    self.assertIn(f'QWidget {{ background-color: {c["widget"]}', css)
                    self.assertIn(f'QDockWidget::title {{ background-color: {c["dock"]}', css)
                    self.assertIn(f'background-color: {c["button"]}; color: {c["text"]};', css)
                    self.assertIn(f'background-color: {c["surface"]}; color: {c["text"]};', css)
                    self.assertIn(f'selection-background-color: {c["accent"]}', css)
                    self.assertIn(f'color: {c["selected_text"]}', css)
                    self.assertGreaterEqual(contrast(c['text'], c['window']), 4.5)
                    self.assertGreaterEqual(contrast(c['text'], c['surface']), 4.5)
                    self.assertGreaterEqual(contrast(c['text'], c['button']), 4.5)
                    self.assertGreaterEqual(contrast(c['selected_text'], c['accent']), 4.5)

    def test_rose_is_a_real_pink_theme_not_only_a_pink_selection(self):
        light = stylesheet_for({'appearance_mode': 'light', 'qt_accent_color': 'pink'})
        dark = stylesheet_for({'appearance_mode': 'dark', 'qt_accent_color': 'pink'})
        for token in ('#f3e5ed', '#fff5fa', '#eed3e1', '#ad246a'):
            self.assertIn(token, light)
        for token in ('#21141e', '#301e2b', '#4c3043', '#b3447c'):
            self.assertIn(token, dark)
        self.assertIn('QTabBar::tab:selected { background: #9f235f; color: #ffffff;', light)
        self.assertIn('QTabBar::tab:selected { background: #a93576; color: #ffffff;', dark)

    def test_old_standard_appearance_and_windows_are_unchanged(self):
        self.assertTrue(stylesheet_for({'appearance_mode': 'dark'}).startswith(DARK_STYLE))
        self.assertIn('#f3f6fb', stylesheet_for({'appearance_mode': 'light'}))
        self.assertEqual(stylesheet_for({'appearance_mode': 'system', 'qt_palette_preset': 'rose'}), '')
        self.assertIsNone(active_palette({'appearance_mode': 'system'}))
        self.assertIsNone(active_palette({'appearance_mode': 'dark', 'qt_palette_preset': 'standard'}))

    def test_custom_colours_apply_to_major_controls(self):
        c = dict(window='#f6ebf2', surface='#fff9fc', button='#e8d3df',
                 accent='#9d1c65', text='#302332')
        self.assertEqual(normalize_custom_colors(c), c)
        palette = palette_colors('light', 'custom', c)
        css = stylesheet_for({'appearance_mode': 'light', 'qt_palette_preset': 'custom',
                              'qt_custom_colors': c})
        self.assertIn('QMainWindow { background-color: #f6ebf2;', css)
        self.assertIn('QWidget { background-color: '+palette['widget'], css)
        self.assertIn('QDockWidget::title { background-color: '+palette['dock'], css)
        self.assertIn('background-color: #e8d3df; color: #302332;', css)
        self.assertIn('selection-background-color: #9d1c65;', css)

    def test_custom_rejects_low_contrast_and_css_injection(self):
        examples = [
            dict(window='#ffffff', surface='#ffffff', button='#ffffff', accent='#ffffff', text='#ffffff'),
            dict(window='#ffffff', surface='#ffffff', button='#ffffff', accent='#123456', text='#cccccc'),
            dict(window='#ffffff', surface='#ffffff', button='#ffffff', accent='#123456; }QWidget{}', text='#000000'),
            {'window': '#ffffff'},
            ['#ffffff'],
        ]
        for case in examples:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    normalize_custom_colors(case)
                with self.assertRaises(ValueError):
                    validate_display_preferences({'qt_custom_colors': case})
        self.assertEqual(selected_text('#ffffff'), '#151515')
        self.assertEqual(selected_text('#111111'), '#ffffff')
        with self.assertRaises(ValueError):
            validate_display_preferences({'qt_palette_preset': 'custom'})
        with self.assertRaises(ValueError):
            validate_display_preferences({'qt_palette_preset': 'bright-nonsense'})

    def test_empty_invalid_saved_custom_falls_back_without_crashing(self):
        css = stylesheet_for({'appearance_mode': 'dark', 'qt_palette_preset': 'custom',
                              'qt_custom_colors': {}})
        self.assertIn('QMainWindow { background-color:', css)

    def test_custom_settings_survive_json_roundtrip_as_dictionary(self):
        import settings
        custom = dict(window='#f6ebf2', surface='#fff9fc', button='#e8d3df',
                      accent='#9d1c65', text='#302332')
        validated = validate_display_preferences({
            'appearance_mode': 'light', 'qt_palette_preset': 'custom',
            'qt_custom_colors': custom,
        })
        self.assertEqual(validated['qt_custom_colors'], custom)
        with tempfile.TemporaryDirectory() as t:
            filepath = Path(t)/'config.json'
            with patch.object(settings, 'CONFIG_PATH', filepath):
                save_config(validated)
                loaded = load_config()
                raw = json.loads(filepath.read_text(encoding='utf-8'))
            self.assertIsInstance(raw['qt_custom_colors'], dict)
            self.assertEqual(loaded['qt_custom_colors'], custom)
            self.assertEqual(loaded['qt_palette_preset'], 'custom')
        self.assertIn("updated.update(display)", API)
        self.assertIn("if key != 'operation_visibility' and key != 'qt_custom_colors'", API)


class UIPaletteContracts(unittest.TestCase):
    def test_custom_modal_stages_edits_until_setup_save(self):
        tree = ast.parse(SETUP)
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        self.assertIn('_CustomPaletteDialog', classes)
        self.assertIn('DwmSetupDialog', classes)
        self.assertIn('QColorDialog.getColor(', SETUP)
        self.assertIn('normalize_custom_colors(self.colors', SETUP)
        self.assertIn("self.palette_combo.addItem(label, key)", SETUP)
        self.assertIn("self._refresh_palette_preview(selected, preset)", SETUP)
        self.assertIn("result['qt_palette_preset']", SETUP)
        self.assertIn("result['qt_custom_colors'] = dict(self._custom_colors)", SETUP)
        self.assertIn("self.custom_button.clicked.connect(self._open_custom_palette)", SETUP)
        self.assertIn("self.palette_combo.currentIndexChanged.connect(self._palette_changed)", SETUP)
        self.assertNotIn('save_config(', SETUP)
        self.assertNotIn('.mkdir(', SETUP)

    def test_cancelled_custom_palette_restores_previous_selection(self):
        tree = ast.parse(SETUP)
        dialog = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DwmSetupDialog')
        method = next(n for n in dialog.body if isinstance(n, ast.FunctionDef) and n.name == '_palette_changed')
        ns = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                     '<palette_combo>', 'exec'), ns)
        class Combo:
            def __init__(self): self.selected = 'custom'; self.blocked = False
            def currentData(self): return self.selected
            def findData(self, v): return 0 if v == 'standard' else 1
            def setCurrentIndex(self, v): self.selected = 'standard' if v == 0 else 'custom'
            def blockSignals(self, v): self.blocked = bool(v)
        class Window:
            _palette_changed = ns['_palette_changed']
            def __init__(self):
                self.palette_combo = Combo(); self._custom_colors = {}
                self._previous_palette = 'standard'; self.refreshes = 0
            def _open_custom_palette(self): return False
            def _refresh_appearance_explanation(self): self.refreshes += 1
        fake = Window()
        fake._palette_changed(1)
        self.assertEqual(fake.palette_combo.currentData(), 'standard')
        self.assertFalse(fake.palette_combo.blocked)
        self.assertEqual(fake.refreshes, 1)


if __name__ == '__main__':
    unittest.main()
