"""a3 headless regression tests: themes, atomic settings, popup geometry."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest
import tomllib
from unittest.mock import patch
import tempfile

from app.presentation_preferences_v0110_a3 import validate_display_preferences
from gui_qt.appearance_v0110_a3 import (
    THEME_CHOICES, ACCENT_CHOICES, theme_mode, accent_mode, stylesheet_for,
)
from gui_qt.window_placement_v0110_a3 import (
    Rect, PLACEMENT_CHOICES, placement_mode, plan_popup,
)
from settings import DEFAULT_CONFIG
from version import VERSION

ROOT = Path(__file__).resolve().parents[1]


class PreferenceTests(unittest.TestCase):
    def test_system_is_default_on_new_install(self):
        self.assertEqual(DEFAULT_CONFIG['appearance_mode'], 'system')
        self.assertEqual(DEFAULT_CONFIG['qt_accent_color'], 'system')
        self.assertEqual(DEFAULT_CONFIG['qt_popup_placement'], 'auto')
        self.assertEqual(theme_mode({}), 'system')
        self.assertEqual(accent_mode({}), 'system')

    def test_three_theme_and_six_accent_choices(self):
        self.assertEqual(set(THEME_CHOICES), {'system', 'dark', 'light'})
        self.assertEqual(len(ACCENT_CHOICES), 6)
        self.assertEqual(set(PLACEMENT_CHOICES), {'auto', 'over', 'beside'})

    def test_config_roundtrip_preserves_explicit_choice(self):
        import settings
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(settings, 'CONFIG_PATH', Path(tmp) / 'config.json'):
                settings.save_config({'appearance_mode': 'dark',
                                      'qt_accent_color': 'green',
                                      'qt_popup_placement': 'beside'})
                loaded = settings.load_config()
        self.assertEqual(loaded['appearance_mode'], 'dark')
        self.assertEqual(loaded['qt_accent_color'], 'green')
        self.assertEqual(loaded['qt_popup_placement'], 'beside')

    def test_persistence_validation(self):
        for value in ('dark', 'light', 'system'):
            self.assertEqual(validate_display_preferences({'appearance_mode': value})['appearance_mode'], value)
        self.assertEqual(validate_display_preferences({'qt_accent_color':'purple'})['qt_accent_color'], 'purple')
        self.assertEqual(validate_display_preferences({'qt_popup_placement': 'beside'})['qt_popup_placement'], 'beside')
        for key, value in [('appearance_mode','blue'), ('qt_accent_color','red'), ('qt_popup_placement','outside')]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    validate_display_preferences({key: value})

    def test_dark_style_preserves_current_background_and_light_is_distinct(self):
        dark = stylesheet_for({'appearance_mode': 'dark'})
        light = stylesheet_for({'appearance_mode': 'light'})
        native = stylesheet_for({'appearance_mode': 'system'})
        self.assertIn('#10141c', dark)
        self.assertIn('#f3f6fb', light)
        self.assertIn('#ffffff', light)
        self.assertNotIn('QMainWindow, QWidget { background-color: #10141c', light)
        self.assertEqual(native, '')
        for css in (dark,light):
            self.assertIn('dwmStorageProfileCard[chosen="true"]', css)
            self.assertIn('dwmSetupInfo', css)
            self.assertIn('dwmProfileSummary', css)

    def test_accent_applies_to_dark_and_light(self):
        dark_blue = stylesheet_for({'appearance_mode':'dark', 'qt_accent_color': 'blue'})
        dark_green = stylesheet_for({'appearance_mode':'dark', 'qt_accent_color': 'green'})
        light_purple = stylesheet_for({'appearance_mode':'light', 'qt_accent_color': 'purple'})
        self.assertNotEqual(dark_blue,dark_green)
        self.assertIn('#328766', dark_green)
        self.assertIn('#dcccf4', light_purple)
        self.assertEqual(stylesheet_for({'appearance_mode':'system','qt_accent_color':'purple'}), '')

    def test_auto_placement_depends_on_window_role(self):
        self.assertEqual(placement_mode({}, kind='setup'), 'over')
        self.assertEqual(placement_mode({}, kind='editor'), 'over')
        self.assertEqual(placement_mode({}, kind='report'), 'beside')
        self.assertEqual(placement_mode({}, kind='results'), 'beside')
        self.assertEqual(placement_mode({'qt_popup_placement':'over'}, kind='report'),'over')
        self.assertEqual(placement_mode({'qt_popup_placement':'beside'}, kind='setup'),'beside')


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.monitor = Rect(0,0,1920,1080)

    def test_centered_on_main_window(self):
        parent = Rect(150,100,1000,780)
        result, actual = plan_popup(parent,(880,640),(660,490),[self.monitor],mode='over')
        self.assertEqual(actual,'over')
        self.assertEqual((result.width,result.height),(880,640))
        self.assertEqual((result.x,result.y),(210,170))

    def test_right_side_and_size_preserved(self):
        parent = Rect(100,80,900,690)
        result, actual = plan_popup(parent,(850,760),(720,570),[self.monitor],mode='beside')
        self.assertEqual(actual,'beside')
        self.assertGreaterEqual(result.x,parent.right+8)
        self.assertEqual(result.width,850)
        self.assertLessEqual(result.right,self.monitor.right)

    def test_left_side_if_right_is_full(self):
        parent = Rect(1100,80,700,650)
        result, actual = plan_popup(parent,(850,760),(720,570),[self.monitor],mode='beside')
        self.assertEqual(actual,'beside')
        self.assertLessEqual(result.right,parent.x-8)

    def test_shrink_to_minimum_without_moving_main(self):
        parent = Rect(0,0,1180,900)
        result, actual = plan_popup(parent,(850,760),(720,570),[self.monitor],mode='beside')
        self.assertEqual(actual,'beside')
        self.assertGreaterEqual(result.width,720)
        self.assertLess(result.width,850)
        self.assertEqual(parent,Rect(0,0,1180,900))

    def test_use_second_monitor(self):
        main = Rect(0,0,1920,1040)
        second = Rect(1920,0,1920,1080)
        result, actual = plan_popup(main,(1280,800),(760,540),[self.monitor, second], mode='beside')
        self.assertEqual(actual,'beside')
        self.assertGreaterEqual(result.x, second.x)
        self.assertLessEqual(result.right,second.right)

    def test_fallback_to_center_when_no_side_fit(self):
        parent = Rect(0,0,1366,768)
        monitor = Rect(0,0,1366,768)
        result, actual = plan_popup(parent,(850,760),(720,570),[monitor],mode='beside')
        self.assertEqual(actual,'over')
        self.assertGreaterEqual(result.x, 0)
        self.assertLessEqual(result.right,monitor.right)
        self.assertLessEqual(result.bottom,monitor.bottom)

    def test_unknown_mode_and_empty_screens_rejected(self):
        with self.assertRaises(ValueError):
            plan_popup(Rect(0,0,500,500),(400,400),(100,100),[],mode='beside')
        with self.assertRaises(ValueError):
            plan_popup(Rect(0,0,500,500),(400,400),(100,100),[self.monitor],mode='leftish')


class WiringContractTests(unittest.TestCase):
    def test_complete_version(self):
        # a3 remains a required regression, but later alphas are valid.
        self.assertRegex(VERSION, r'^0\.1\.10-a[0-9]+$')
        self.assertGreaterEqual(int(VERSION.rsplit('-a', 1)[1]), 3)
        with (ROOT/'pyproject.toml').open('rb') as f:
            self.assertEqual(tomllib.load(f)['project']['version'], VERSION.replace('-a', 'a'))

    def test_setup_persists_all_display_choices_with_save(self):
        s=(ROOT/'gui_qt/setup_v0110_a3.py').read_text('utf-8')
        ast.parse(s)
        self.assertIn("self._build_appearance_tab()",s)
        self.assertIn("'qt_popup_placement'",s)
        self.assertIn("'appearance_mode'",s)
        self.assertIn("'qt_accent_color'",s)
        self.assertNotIn('save_config(',s)
        api=(ROOT/'app/workbench_api_v0110_a1.py').read_text('utf-8')
        ast.parse(api)
        self.assertIn('validate_display_preferences(changes)',api)
        self.assertIn('saved = save_config(updated)',api)

    def test_startup_and_open_windows_use_new_choices(self):
        startup=(ROOT/'gui_qt/__main__.py').read_text('utf-8')
        main=(ROOT/'gui_qt/main_window.py').read_text('utf-8')
        for s in (startup,main):
            ast.parse(s)
        self.assertLess(startup.index('apply_appearance(application, api.settings)'),startup.index('window = DwmMainWindow(api)'))
        self.assertIn('from gui_qt.setup_v0110_a3 import DwmSetupDialog',main)
        self.assertIn('self._a3_apply_display_preferences()',main)
        self.assertIn("self._a3_place_dialog(dialog, 'setup')",main)
        self.assertIn("self._a3_place_dialog(dialog, 'results')",main)
        self.assertIn("self._a3_place_dialog(dialog, 'report')",main)

    def test_a2_cards_no_longer_force_dark_palette(self):
        s=(ROOT/'gui_qt/setup_v0110_a2.py').read_text('utf-8')
        self.assertNotIn('color: #edf4fc',s)
        self.assertNotIn("background: #192638",s)
        self.assertNotIn('border =',s)
        self.assertIn("setProperty('chosen', chosen)",s)


if __name__=='__main__':
    unittest.main()
