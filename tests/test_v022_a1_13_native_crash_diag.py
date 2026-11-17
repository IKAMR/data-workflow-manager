"""Pure Python regression tests for the optional Windows Qt crash diagnostics.

The crash is native (0xc0000005), so headless tests validate safe/normal
startup wiring and output capture, not Windows C++ safety itself.
"""
from __future__ import annotations

import ast
from contextlib import redirect_stderr
import importlib.util
import io
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'gui_qt' / '__main__.py'


def load_gui_main():
    spec = importlib.util.spec_from_file_location('dwm_tested_gui_main', MAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_gui_modules(events):
    """Provide a pure Python stand-in for all external GUI dependencies."""
    modules = {}

    def module(name, **attributes):
        item = types.ModuleType(name)
        for attr, value in attributes.items():
            setattr(item, attr, value)
        modules[name] = item
        return item

    def record(name, result=None):
        def action(*_args, **_kwargs):
            events.append(name)
            return result
        return action

    class QApplication:
        def __init__(self, _args):
            events.append('qt_construct')
        def setOrganizationName(self, _value):
            pass
        def setApplicationName(self, _value):
            pass
        def exec(self):
            events.append('qt_eventloop')
            return 0

    class QMessageBox:
        @staticmethod
        def warning(*_args):
            events.append('warning')

    class Workbench:
        def __init__(self):
            events.append('api')
            self.settings = {}

    class StableWindow:
        pass

    class MainWindow(StableWindow):
        def __init__(self, _api):
            events.append('window_construct')
            self._v022_fit_ready = True
        def show(self):
            events.append('window_show')
        def open_job_list(self, _path):
            events.append('open_job_list')

    module('PySide6.QtWidgets', QApplication=QApplication, QMessageBox=QMessageBox)
    module('gui_qt.bootstrap_v0113_a1', install=record('bootstrap'))
    module('gui_qt.main_v020_a6', DwmMainWindow=StableWindow)
    module('gui_qt.basic_multijob_v022_a1_2', DwmMainWindow=MainWindow)
    module('gui_qt.canonical_results_v0115_a3', install_canonical_results_menu=record('results'))
    module('gui_qt.start_shell_v020_a1', install_setup_tab=record('setup_tab'),
           install_start_navigation=record('navigation'))
    module('gui_qt.production_home_v020_a2', ProductionStartPage=object,
           install_integrated_home=record('home'))
    module('gui_qt.depot_profile_v022_a1', install_depot_profile_controls=record('depot', True))
    module('app.workbench_api_v020_a2', DwmWorkbenchAPI=Workbench)
    module('gui_qt.appearance_v0110_a3', apply_appearance=record('appearance'))
    module('gui_qt.combobox_popup_v020_a2', install_dropdown_positioning=record('popup_filter'))
    module('gui_qt.file_dialog_contrast_v022_a1_10',
           install_file_dialog_navigation_contrast=record('dialog_filter'))
    module('gui_qt.setup_reset_v022_a1_5', install_setup_reset_actions=record('setup_reset'))
    return modules, MainWindow


class TestNativeCrashDiagnostics(unittest.TestCase):
    def test_main_imports_and_has_no_column_plugin_installation(self):
        text = MAIN.read_text(encoding='utf-8')
        ast.parse(text)
        self.assertNotIn('install_editable_workflow_columns', text)
        self.assertNotIn('workflow_columns_v022_a1_11', text)

    def test_default_starts_with_conservative_gui_features(self):
        events = []
        modules, _window = fake_gui_modules(events)
        main = load_gui_main()
        with patch.dict(sys.modules, modules), patch.dict(os.environ, {'DWM_CRASH_DIAG': '0', 'DWM_SAFE_MODE': '0'}), patch.object(sys, 'argv', ['gui_qt']):
            self.assertEqual(main.main(), 0)
        self.assertNotIn('dialog_filter', events)
        self.assertNotIn('popup_filter', events)
        self.assertIn('window_show', events)
        self.assertLess(events.index('window_show'), events.index('qt_eventloop'))

    def test_safe_mode_skips_only_optional_features(self):
        events = []
        modules, window = fake_gui_modules(events)
        main = load_gui_main()
        created = []
        original = window.__init__
        def track(instance, api):
            original(instance, api)
            created.append(instance)
        with patch.object(window, '__init__', track), patch.dict(sys.modules, modules), patch.dict(os.environ, {'DWM_CRASH_DIAG': '0', 'DWM_SAFE_MODE': '1'}), patch.object(sys, 'argv', ['gui_qt']):
            self.assertEqual(main.main(), 0)
        self.assertNotIn('dialog_filter', events)
        self.assertNotIn('popup_filter', events)
        self.assertEqual(created[0]._v022_fit_ready, False)
        for feature in ('bootstrap','api','appearance','setup_tab','setup_reset','results',
                        'navigation','home','depot','window_show','qt_eventloop'):
            self.assertIn(feature, events)

    def test_debug_markers_flush_before_window_and_event_loop(self):
        events = []
        modules, _window = fake_gui_modules(events)
        main = load_gui_main()
        output = io.StringIO()
        with patch.dict(sys.modules, modules), patch.dict(os.environ, {'DWM_CRASH_DIAG': '1', 'DWM_SAFE_MODE': '0'}), patch.object(sys, 'argv', ['gui_qt']), redirect_stderr(output):
            self.assertEqual(main.main(), 0)
        log = output.getvalue()
        for marker in ('[DWM-BOOT] 01 Python launched', '[DWM-BOOT] 05 QApplication created',
                       '[DWM-BOOT] 11 Setup hooks installed', '[DWM-BOOT] 12 Main window constructed',
                       '[DWM-BOOT] 18 window.show completed', '[DWM-BOOT] 19 Entering Qt event loop',
                       '[DWM-BOOT] 20 Qt event loop returned'):
            self.assertIn(marker, log)
        self.assertLess(log.index('01 Python'), log.index('20 Qt'))

    def test_bats_turn_on_fatal_tracing_without_editing_settings(self):
        debug = (ROOT / 'start-debug.bat').read_text(encoding='utf-8')
        safe = (ROOT / 'start-safe.bat').read_text(encoding='utf-8')
        for key in ('DWM_CRASH_DIAG=1', 'PYTHONFAULTHANDLER=1', 'PYTHONUNBUFFERED=1',
                    'dwm-startup-', 'call "%~dp0start.bat"'):
            self.assertIn(key, debug)
        self.assertIn('DWM_SAFE_MODE=1', safe)
        self.assertIn('call "%~dp0start-debug.bat"', safe)
        self.assertNotIn('config.json', debug + safe)
        self.assertNotIn('.n5jobs', debug + safe)


if __name__ == '__main__':
    unittest.main()
