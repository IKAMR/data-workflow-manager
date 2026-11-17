"""Regression checks for v0.2.2-a1.5, requiring no Qt or filesystem changes."""
from __future__ import annotations

import ast
import json
import sys
import types
from enum import IntFlag
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from settings import DEFAULT_CONFIG
from app.setup_reset_v022_a1_5 import restore_startup, startup_defaults
from app.ui_start_preferences_v020_a2 import UI_DEFAULTS, validate_ui_preferences


class _FakeApi:
    def __init__(self, settings, running=False):
        self.settings = dict(settings)
        self.running = running
        self.changes = []
        self.reloaded = False

    def save_setup(self, values):
        update = validate_ui_preferences(values)
        self.settings.update(update)
        self.changes.append(dict(update))

    def reload_setup(self):
        self.reloaded = True


class TestStartupReset(unittest.TestCase):
    def test_new_default_opens_enkel_not_depot_home(self):
        self.assertEqual(DEFAULT_CONFIG['ui_startup_mode'], 'basic')
        self.assertEqual(DEFAULT_CONFIG['ui_startup_page'], 'control')
        self.assertEqual(UI_DEFAULTS['ui_startup_mode'], 'basic')
        self.assertEqual(UI_DEFAULTS['ui_startup_page'], 'control')

    def test_restore_startup_preserves_depot_and_external_tools(self):
        current = {
            'ui_work_profile': 'depot',
            'ui_startup_mode': 'advanced',
            'ui_startup_page': 'home',
            'arkade5_cli_path': r'C:\tools\arkade.exe',
            'app_work_subfolder': 'repository_operations',
            'last_job_list_file': r'D:\saved\three-jobs.n5jobs',
        }
        api = _FakeApi(current)
        result = restore_startup(api)
        self.assertEqual(result, {'ui_startup_mode': 'basic', 'ui_startup_page': 'control'})
        for name in ('ui_work_profile', 'arkade5_cli_path', 'app_work_subfolder', 'last_job_list_file'):
            self.assertEqual(api.settings[name], current[name])
        self.assertTrue(api.reloaded)
        self.assertEqual(len(api.changes), 1)

    def test_reset_rejected_while_running(self):
        api = _FakeApi({'ui_startup_page': 'home'}, running=True)
        with self.assertRaises(RuntimeError):
            restore_startup(api)
        self.assertEqual(api.changes, [])
        self.assertFalse(api.reloaded)

    def test_invalid_api_save_does_not_reload(self):
        api = _FakeApi({'ui_startup_page': 'home'})
        def fail(_changes):
            raise ValueError('disken er skrivebeskyttet')
        api.save_setup = fail
        with self.assertRaisesRegex(ValueError, 'skrivebeskyttet'):
            restore_startup(api)
        self.assertFalse(api.reloaded)

    def test_builtin_full_reset_includes_new_ui_defaults(self):
        from app import settings_portable
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / 'config.json'
            work = root / 'work' / 'resultat.json'
            jobs = root / 'test.n5jobs'
            work.parent.mkdir()
            work.write_text('rapporten er bevart', encoding='utf-8')
            jobs.write_text('jobblisten er bevart', encoding='utf-8')
            config.write_text(json.dumps({
                'ui_work_profile': 'depot', 'ui_startup_mode': 'advanced',
                'ui_startup_page': 'home', 'arkade5_cli_path': 'C:/arkade5.exe',
            }), encoding='utf-8')
            with patch.object(settings_portable, 'CONFIG_PATH', config):
                changed = settings_portable.reset_settings()
                readback = json.loads(config.read_text(encoding='utf-8'))
            self.assertEqual(changed['ui_startup_page'], 'control')
            self.assertEqual(readback['ui_startup_page'], 'control')
            self.assertEqual(readback['ui_startup_mode'], 'basic')
            self.assertEqual(readback['arkade5_cli_path'], '')
            self.assertEqual(jobs.read_text(encoding='utf-8'), 'jobblisten er bevart')
            self.assertEqual(work.read_text(encoding='utf-8'), 'rapporten er bevart')

    def test_portable_export_keeps_new_ui_keys(self):
        from app import settings_portable
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / 'config.json'
            config.write_text(json.dumps({
                'ui_work_profile': 'depot', 'ui_startup_page': 'home',
                'ui_startup_mode': 'advanced',
            }), encoding='utf-8')
            output = root / 'dwm-setup.json'
            with patch.object(settings_portable, 'CONFIG_PATH', config):
                settings_portable.export_settings(output)
            exported = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(exported['settings']['ui_work_profile'], 'depot')
            self.assertEqual(exported['settings']['ui_startup_page'], 'home')

    def test_gui_wire_order_and_two_existing_reset_scopes(self):
        root = Path(__file__).resolve().parent.parent
        launch = (root / 'gui_qt' / '__main__.py').read_text(encoding='utf-8')
        tree = ast.parse(launch)
        self.assertTrue(tree)
        self.assertLess(launch.index('install_setup_tab()'),
                        launch.index('install_setup_reset_actions()'))
        self.assertLess(launch.index('install_setup_reset_actions()'),
                        launch.index('window = DwmMainWindow(api)'))
        adapter = (root / 'gui_qt' / 'setup_reset_v022_a1_5.py').read_text(encoding='utf-8')
        ast.parse(adapter)
        self.assertIn('Tilbakestill oppstart', adapter)
        self.assertIn('Tilbakestill alle Setup-innstillinger', adapter)
        self.assertIn('self.reset_button', adapter)


    def test_setup_wrapper_reuses_full_reset_button_and_runs_startup_reset(self):
        from gui_qt.setup_reset_v022_a1_5 import install_setup_reset_actions

        class Signal:
            def __init__(self):
                self.callback = None
            def connect(self, callback):
                self.callback = callback

        class Button:
            def __init__(self, caption, parent=None):
                self.caption = caption
                self.clicked = Signal()
                self.object_name = ''
            def setText(self, value):
                self.caption = value
            def setToolTip(self, value):
                self.tooltip = value
            def setObjectName(self, value):
                self.object_name = value

        class Label:
            def __init__(self, caption, parent=None):
                self.caption = caption
            def setWordWrap(self, enabled):
                self.wrapped = enabled

        class Layout:
            def __init__(self):
                self.widgets = []
            def addWidget(self, widget):
                self.widgets.append(widget)

        class Page:
            def __init__(self):
                self._layout = Layout()
            def layout(self):
                return self._layout

        class Status(IntFlag):
            Yes = 1
            No = 2

        class MessageBox:
            StandardButton = Status
            @staticmethod
            def question(*args, **kwargs):
                return Status.Yes
            @staticmethod
            def information(*args, **kwargs):
                pass
            @staticmethod
            def warning(*args, **kwargs):
                raise AssertionError('Unexpected warning')

        class ExistingSetup:
            def __init__(self, api, parent=None):
                self.api = api
                self.startup_page = Page()
                self.reset_button = Button('Nullstill setup')
                self.reset_button.clicked.connect(self._reset)
                self.accepted = False
            def _reset(self):
                self.original_reset_called = True
            def accept(self):
                self.accepted = True

        qt_pkg = types.ModuleType('PySide6')
        qt_pkg.__path__ = []
        widgets = types.ModuleType('PySide6.QtWidgets')
        widgets.QLabel = Label
        widgets.QMessageBox = MessageBox
        widgets.QPushButton = Button
        setup = types.ModuleType('gui_qt.setup_format_v0111_a2')
        setup.DwmSetupDialog = ExistingSetup
        with patch.dict(sys.modules, {
            'PySide6': qt_pkg,
            'PySide6.QtWidgets': widgets,
            'gui_qt.setup_format_v0111_a2': setup,
        }):
            install_setup_reset_actions()
            self.assertTrue(issubclass(setup.DwmSetupDialog, ExistingSetup))
            api = _FakeApi({'ui_work_profile': 'depot',
                            'ui_startup_page': 'home',
                            'ui_startup_mode': 'advanced'})
            dialog = setup.DwmSetupDialog(api)
            self.assertEqual(dialog.reset_button.caption,
                             'Tilbakestill alle Setup-innstillinger…')
            self.assertEqual(dialog.v022_reset_startup_button.object_name,
                             'v022_setup_reset_startup')
            self.assertIsNotNone(dialog.reset_button.clicked.callback)
            dialog.v022_reset_startup_button.clicked.callback()
            self.assertTrue(dialog.accepted)
            self.assertEqual(api.settings['ui_work_profile'], 'depot')
            self.assertEqual(api.settings['ui_startup_page'], 'control')
            self.assertEqual(api.settings['ui_startup_mode'], 'basic')
            self.assertEqual(len(dialog.startup_page.layout().widgets), 2)
            # Installing the same patch twice must not stack wrapper classes.
            original_wrapper = setup.DwmSetupDialog
            install_setup_reset_actions()
            self.assertIs(setup.DwmSetupDialog, original_wrapper)


if __name__ == '__main__':
    unittest.main()
