"""v0.2.0-a1: headless checks of the Qt startup policy and wiring."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
START = ROOT / 'gui_qt' / 'start_shell_v020_a1.py'
ENTRY = ROOT / 'gui_qt' / '__main__.py'


def policy():
    """Load pure startup rules without requiring PySide6 in CI."""
    original = ast.parse(START.read_text(encoding='utf8'))
    constants = {'PROFILE_KEY', 'STARTUP_KEY', 'FEATURES_KEY', 'PROFILES', 'STARTUP_MODES', 'SECTIONS'}
    functions = {'normalize_profile', 'normalize_startup', 'normalize_sections', 'visible_sections', 'startup_target'}
    nodes = [n for n in original.body if (
        isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets)
    ) or (isinstance(n, ast.FunctionDef) and n.name in functions)]
    tree = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    result = {}
    exec(compile(tree, str(START), 'exec'), result)
    return result


class StartupA1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = policy()

    def test_new_user_opens_basic_with_control_only(self):
        self.assertEqual(self.rules['startup_target']({}, 'advanced'), 'basic')
        self.assertEqual(self.rules['visible_sections']({}), ['control'])

    def test_last_used_respects_saved_mode(self):
        f = self.rules['startup_target']
        self.assertEqual(f({'ui_startup_mode': 'last'}, 'advanced'), 'advanced')
        self.assertEqual(f({'ui_startup_mode': 'last'}, 'basic'), 'basic')

    def test_fixed_mode_does_not_depend_on_last(self):
        f = self.rules['startup_target']
        self.assertEqual(f({'ui_startup_mode': 'advanced'}, 'basic'), 'advanced')
        self.assertEqual(f({'ui_startup_mode': 'basic'}, 'advanced'), 'basic')

    def test_depot_and_custom_profiles(self):
        v = self.rules['visible_sections']
        self.assertEqual(len(v({'ui_work_profile': 'depot'})), 8)
        self.assertEqual(v({'ui_work_profile': 'custom', 'ui_visible_sections': ['report', 'unknown', 'control', 'report']}), ['report', 'control'])

    def test_invalid_settings_use_safe_defaults(self):
        self.assertEqual(self.rules['visible_sections']({'ui_work_profile': 'invalid'}), ['control'])
        self.assertEqual(self.rules['startup_target']({'ui_startup_mode': 'invalid'}, 'advanced'), 'basic')

    def test_entrypoint_keeps_existing_engine_and_switch(self):
        source = ENTRY.read_text(encoding='utf8')
        self.assertIn('install_start_navigation(window)', source)
        self.assertIn('install_setup_tab()', source)
        self.assertIn('DwmWorkbenchAPI()', source)
        self.assertIn('DwmMainWindow(api)', source)
        shell = START.read_text(encoding='utf8')
        self.assertIn('window._leave_basic()', shell)
        self.assertIn('window._enter_basic()', shell)
        self.assertIn('window.basic_advanced_button', shell)


if __name__ == '__main__':
    unittest.main()
