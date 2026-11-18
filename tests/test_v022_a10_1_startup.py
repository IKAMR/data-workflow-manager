"""A10.1 regression: Qt startup tests use only minimal Qt stand-ins.

The old a1.13/a1.14 tests must be able to instantiate their fake window
without importing QtCore or building A10 presentation widgets.  The real
window still installs those widgets when its toolbar is present.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _module(name, **attributes):
    m = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(m, key, value)
    return m


class StartupWithFakeQt(unittest.TestCase):
    def test_a10_module_imports_without_qtcore(self):
        class LegacyWindow:
            def __init__(self, api):
                self.api = api
                self._v022_fit_ready = True

        fake_modules = {
            'PySide6': _module('PySide6'),
            'PySide6.QtCore': None,  # an attempted QtCore import must fail
            'PySide6.QtWidgets': _module('PySide6.QtWidgets'),
            'gui_qt.basic_multijob_v022_a1_2': _module(
                'gui_qt.basic_multijob_v022_a1_2', DwmMainWindow=LegacyWindow),
        }
        with patch.dict(sys.modules, fake_modules):
            spec = importlib.util.spec_from_file_location(
                'a10_1_mock_import', ROOT/'gui_qt/main_v022_a10.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            window = module.DwmMainWindow(object())
            self.assertTrue(isinstance(window, LegacyWindow))
            self.assertTrue(window._v022_fit_ready)

    def test_real_entrypoint_uses_fake_qt_and_preserves_boot_features(self):
        for safe_mode, optin in ((False, None), (True, None),
                                 (False, 'dialog'), (False, 'popup'),
                                 (False, 'fit')):
            with self.subTest(safe_mode=safe_mode, optin=optin):
                events = []

                def record(label, result=None):
                    def callback(*args, **kwargs):
                        events.append(label)
                        return result
                    return callback

                class Application:
                    def __init__(self, argv):
                        events.append('qt_construct')
                    def setOrganizationName(self, name):
                        pass
                    def setApplicationName(self, name):
                        pass
                    def exec(self):
                        events.append('qt_eventloop')
                        return 0

                class QtMessageBox:
                    warning = staticmethod(record('warning'))

                class Api:
                    def __init__(self):
                        self.settings = {}
                        events.append('api')

                class StableWindow:
                    pass

                class FakeBase(StableWindow):
                    def __init__(self, api):
                        self._v022_fit_ready = True
                        self.api = api
                        events.append('window_construct')
                    def show(self):
                        events.append('window_show')
                    def open_job_list(self, path):
                        events.append('open_joblist')

                def select_features(_environment):
                    from types import SimpleNamespace
                    return SimpleNamespace(
                        safe_mode=safe_mode,
                        dialog_filter=bool(optin == 'dialog' and not safe_mode),
                        popup_filter=bool(optin == 'popup' and not safe_mode),
                        basic_auto_fit=bool(optin == 'fit' and not safe_mode),
                    )

                modules = {
                    'PySide6': _module('PySide6'),
                    'PySide6.QtCore': None,
                    'PySide6.QtWidgets': _module('PySide6.QtWidgets', QApplication=Application, QMessageBox=QtMessageBox),
                    'gui_qt.main_v020_a6': _module('gui_qt.main_v020_a6', DwmMainWindow=StableWindow),
                    'gui_qt.basic_multijob_v022_a1_2': _module('gui_qt.basic_multijob_v022_a1_2', DwmMainWindow=FakeBase),
                    'gui_qt.bootstrap_v0113_a1': _module('gui_qt.bootstrap_v0113_a1', install=record('bootstrap')),
                    'gui_qt.canonical_results_v0115_a3': _module('gui_qt.canonical_results_v0115_a3', install_canonical_results_menu=record('results')),
                    'gui_qt.start_shell_v020_a1': _module('gui_qt.start_shell_v020_a1', install_setup_tab=record('setup_tab'), install_start_navigation=record('navigation')),
                    'gui_qt.setup_reset_v022_a1_5': _module('gui_qt.setup_reset_v022_a1_5', install_setup_reset_actions=record('reset')),
                    'gui_qt.production_home_v020_a2': _module('gui_qt.production_home_v020_a2', ProductionStartPage=object, install_integrated_home=record('home')),
                    'gui_qt.depot_profile_v022_a1': _module('gui_qt.depot_profile_v022_a1', install_depot_profile_controls=record('depot', True)),
                    'app.workbench_api_v020_a2': _module('app.workbench_api_v020_a2', DwmWorkbenchAPI=Api),
                    'gui_qt.appearance_v0110_a3': _module('gui_qt.appearance_v0110_a3', apply_appearance=record('appearance')),
                    'gui_qt.qt_startup_policy_v022_a1_14': _module('gui_qt.qt_startup_policy_v022_a1_14', select_qt_startup_features=select_features),
                    'gui_qt.file_dialog_contrast_v022_a1_10': _module('gui_qt.file_dialog_contrast_v022_a1_10', install_file_dialog_navigation_contrast=record('dialog_filter')),
                    'gui_qt.combobox_popup_v020_a2': _module('gui_qt.combobox_popup_v020_a2', install_dropdown_positioning=record('popup_filter')),
                }
                spec = importlib.util.spec_from_file_location(
                    'a10_1_mock_entrypoint', ROOT/'gui_qt/__main__.py')
                main = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(main)
                with patch.dict(sys.modules, modules), patch.object(sys, 'argv', ['gui_qt']):
                    self.assertEqual(main.main(), 0)
                self.assertIn('window_construct', events)
                self.assertIn('window_show', events)
                self.assertLess(events.index('window_show'), events.index('qt_eventloop'))
                self.assertEqual('dialog_filter' in events, optin == 'dialog' and not safe_mode)
                self.assertEqual('popup_filter' in events, optin == 'popup' and not safe_mode)


if __name__ == '__main__':
    unittest.main()
