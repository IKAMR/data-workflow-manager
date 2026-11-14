"""Regression for a2: accepted UI preferences and embedded home navigation."""
from __future__ import annotations

import ast
from pathlib import Path
from threading import Lock
import unittest

from app.ui_start_preferences_v020_a2 import (
    UI_SETUP_KEYS, validate_ui_preferences,
)

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'gui_qt' / 'production_home_v020_a2.py'
ENTRY = ROOT / 'gui_qt' / '__main__.py'
SHELL = ROOT / 'gui_qt' / 'start_shell_v020_a1.py'
API = ROOT / 'app' / 'workbench_api_v020_a2.py'


class IntegratedHomeA2Tests(unittest.TestCase):
    def test_work_profile_accepts_eight_areas_without_qt(self):
        # Load the a1 pure functions only; PySide6 is not required in test.bat.
        tree = ast.parse(SHELL.read_text(encoding='utf8'))
        names = {'PROFILE_KEY', 'STARTUP_KEY', 'FEATURES_KEY', 'PROFILES',
                 'STARTUP_MODES', 'SECTIONS'}
        functions = {'normalize_profile', 'normalize_startup',
                     'normalize_sections', 'visible_sections'}
        chosen = [node for node in tree.body if
                  (isinstance(node, ast.Assign) and any(
                      isinstance(target, ast.Name) and target.id in names
                      for target in node.targets)) or
                  (isinstance(node, ast.FunctionDef) and node.name in functions)]
        env = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=chosen, type_ignores=[])),
                     str(SHELL), 'exec'), env)
        self.assertEqual(len(env['visible_sections']({'ui_work_profile': 'depot'})), 8)
        self.assertEqual(env['visible_sections']({'ui_work_profile': 'control'}), ['control'])

    def test_ui_preferences_are_typed_and_validated(self):
        self.assertEqual(UI_SETUP_KEYS, {
            'ui_work_profile', 'ui_startup_mode', 'ui_visible_sections',
            'ui_startup_page', 'ui_area_visibility',
        })
        self.assertEqual(validate_ui_preferences({
            'ui_work_profile': 'depot',
            'ui_startup_mode': 'last',
            'ui_visible_sections': ['control', 'report', 'control'],
            'ui_startup_page': 'last',
            'ui_area_visibility': 1,
        }), {
            'ui_work_profile': 'depot',
            'ui_startup_mode': 'last',
            'ui_visible_sections': ['control', 'report'],
            'ui_startup_page': 'last',
            'ui_area_visibility': 1,
        })
        for wrong in (
            {'ui_work_profile': 'unknown'},
            {'ui_startup_mode': 'surprise'},
            {'ui_visible_sections': 'control'},
            {'ui_visible_sections': ['control', '../unsafe']},
            {'ui_startup_page': 'unknown'},
            {'ui_area_visibility': True},
            {'ui_area_visibility': 3},
            {'ui_area_visibility': '0'},
            {'unexpected_setup_key': 1},
        ):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                validate_ui_preferences(wrong)

    def test_api_accepts_profile_and_preserves_legacy_validation(self):
        # Execute only this real API subclass with a minimal prior-layer stub.
        # No Source/Work files or heavy backend dependency are loaded.
        node = next(x for x in ast.parse(API.read_text(encoding='utf8')).body
                    if isinstance(x, ast.ClassDef) and x.name == 'DwmWorkbenchAPI')
        node.bases = [ast.Name(id='_Base', ctx=ast.Load())]
        history = []
        config = {}

        class FakeError(RuntimeError):
            pass

        class Previous:
            def __init__(self):
                self._guard = Lock()
                self.settings = {}
                self.events = []
                self.idle = True

            def _assert_idle(self):
                if not self.idle:
                    raise FakeError('Kjøring pågår')

            def _emit(self, name, message=''):
                self.events.append((name, message))

            def save_setup(self, changes):
                history.append(dict(changes))
                if set(changes) - {'operation_visibility'}:
                    raise FakeError('Ukjente Setup-innstillinger')
                config.update(changes)
                self.settings.update(changes)
                return dict(config)

        def saved(changes):
            config.update(changes)
            return dict(config)

        context = {
            '_Base': Previous,
            'UI_SETUP_KEYS': UI_SETUP_KEYS,
            'validate_ui_preferences': validate_ui_preferences,
            'DwmApiError': FakeError,
            'save_config': saved,
        }
        source = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
        exec(compile(source, str(API), 'exec'), context)
        api = context['DwmWorkbenchAPI']()
        api.save_setup({'ui_work_profile': 'depot', 'ui_startup_page': 'home', 'ui_area_visibility': 0})
        self.assertEqual(config['ui_work_profile'], 'depot')
        self.assertEqual(config['ui_startup_page'], 'home')
        self.assertEqual(config['ui_area_visibility'], 0)
        self.assertEqual(api.settings['ui_work_profile'], 'depot')
        self.assertEqual(history, [])  # UI-only must not call old strict validator
        api.save_setup({'ui_startup_mode': 'advanced', 'ui_visible_sections': ['control'],
                        'operation_visibility': 2})
        self.assertEqual(history, [{'operation_visibility': 2}])
        self.assertEqual(config['ui_visible_sections'], ['control'])
        before = dict(config)
        for invalid in ({'ui_work_profile': 'something_else'},
                        {'ui_visible_sections': 'control'}):
            with self.assertRaises(FakeError):
                api.save_setup(invalid)
            self.assertEqual(config, before)
        api.idle = False
        with self.assertRaises(FakeError):
            api.save_setup({'ui_work_profile': 'control'})
        self.assertEqual(config, before)

    def test_startside_is_a_central_widget_not_a_dialog(self):
        code = HOME.read_text(encoding='utf8')
        self.assertIn('class ProductionStartPage(QWidget):', code)
        self.assertIn('window.takeCentralWidget()', code)
        self.assertIn('QStackedWidget(window)', code)
        self.assertIn('window.setCentralWidget(stack)', code)
        self.assertIn('stack.setCurrentWidget(home)', code)
        self.assertIn('stack.setCurrentWidget(original)', code)
        self.assertNotIn('class ProductionStartPage(QDialog):', code)
        self.assertIn('window.v020_integrated_home = show_home', code)
        self.assertIn('window.v020_show_control_page = show_control', code)
        shell = SHELL.read_text(encoding='utf8')
        self.assertIn('if integrated is not None:', shell)
        self.assertIn('integrated()', shell)
        self.assertIn('return', shell)

    def test_mode_and_existing_advanced_dock_layout_survive_home(self):
        code = HOME.read_text(encoding='utf8')
        self.assertIn('window._basic_active', code)
        self.assertIn('window._leave_basic()', code)
        self.assertIn('window._enter_basic()', code)
        self.assertIn("'docks': {name:", code)
        self.assertIn('RestoreControlBeforeClose', code)
        self.assertIn('window.installEventFilter(', code)
        self.assertNotIn('create_job(', code)
        self.assertNotIn('run_job(', code)

    def test_entrypoint_loads_ui_aware_api_before_showing_window(self):
        code = ENTRY.read_text(encoding='utf8')
        self.assertIn('from app.workbench_api_v020_a2 import DwmWorkbenchAPI', code)
        self.assertIn('install_integrated_home(window)', code)
        self.assertLess(code.index('install_integrated_home(window)'), code.index('window.show()'))


if __name__ == '__main__':
    unittest.main()
