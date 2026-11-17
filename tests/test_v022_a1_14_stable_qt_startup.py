"""Headless startup safety regression checks for DWM v0.2.2-a1.14.

Native Windows Qt painting / structured-exception safety is NOT simulated.
These tests guard the hooks removed from the default startup path and their
explicit opt-in controls, so a future GUI change cannot undo the mitigation.
"""
from __future__ import annotations

import ast
from contextlib import redirect_stderr
from importlib.util import module_from_spec, spec_from_file_location
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from test_v022_a1_13_native_crash_diag import fake_gui_modules, load_gui_main

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'gui_qt' / 'qt_startup_policy_v022_a1_14.py'
MAIN = ROOT / 'gui_qt' / '__main__.py'


def read_policy():
    spec = spec_from_file_location('dwm_qa14_startup_policy', POLICY)
    module = module_from_spec(spec)
    # dataclasses resolves annotations using the module registry
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop(spec.name, None)


def mocked_start(env):
    events = []
    modules, window_class = fake_gui_modules(events)
    constructed = []
    original_init = window_class.__init__

    class FakeFitButton:
        def __init__(self):
            self.hidden = False
        def hide(self):
            events.append('fit_control_hidden')
            self.hidden = True

    def capture(instance, api):
        original_init(instance, api)
        instance.v022_fit_window_button = FakeFitButton()
        constructed.append(instance)

    m = load_gui_main()
    with patch.object(window_class, '__init__', capture), \
         patch.dict(sys.modules, modules), \
         patch.dict(os.environ, env, clear=True), \
         patch.object(sys, 'argv', ['gui_qt']):
        with redirect_stderr(io.StringIO()) as stderr:
            status = m.main()
        logs = stderr.getvalue()
    return status, events, constructed[0], logs


class TestStableQtStartup(unittest.TestCase):
    def test_policy_defaults_to_no_optional_qt_hooks(self):
        policy = read_policy().select_qt_startup_features({})
        self.assertFalse(policy.safe_mode)
        self.assertFalse(policy.dialog_filter)
        self.assertFalse(policy.popup_filter)
        self.assertFalse(policy.basic_auto_fit)

    def test_only_literal_one_enables_one_experiment(self):
        selector = read_policy().select_qt_startup_features
        keys = ('DWM_ENABLE_QT_DIALOG_FILTER', 'DWM_ENABLE_QT_POPUP_FILTER',
                'DWM_ENABLE_QT_BASIC_AUTOFIT')
        for key, field in zip(keys, ('dialog_filter', 'popup_filter', 'basic_auto_fit')):
            with self.subTest(key=key):
                p = selector({key: '1'})
                self.assertTrue(getattr(p, field))
                self.assertEqual(sum((p.dialog_filter, p.popup_filter, p.basic_auto_fit)), 1)
                for invalid in ('true', '0', '', 'enabled'):
                    self.assertFalse(getattr(selector({key: invalid}), field))

    def test_explicit_safe_mode_overrides_every_optin(self):
        p = read_policy().select_qt_startup_features({
            'DWM_SAFE_MODE': '1',
            'DWM_ENABLE_QT_DIALOG_FILTER': '1',
            'DWM_ENABLE_QT_POPUP_FILTER': '1',
            'DWM_ENABLE_QT_BASIC_AUTOFIT': '1',
        })
        self.assertTrue(p.safe_mode)
        self.assertFalse(any((p.dialog_filter, p.popup_filter, p.basic_auto_fit)))

    def test_normal_start_uses_same_safe_hooks_as_previous_safe_mode(self):
        status, events, window, _ = mocked_start({'DWM_CRASH_DIAG': '1'})
        self.assertEqual(status, 0)
        self.assertNotIn('dialog_filter', events)
        self.assertNotIn('popup_filter', events)
        self.assertIn('window_show', events)
        self.assertIn('qt_eventloop', events)
        self.assertEqual(window._v022_fit_ready, False)
        self.assertTrue(window.v022_fit_window_button.hidden)
        self.assertLess(events.index('fit_control_hidden'), events.index('window_show'))

    def test_dialog_optin_does_not_enable_popup_or_fit(self):
        status, events, window, _ = mocked_start({
            'DWM_ENABLE_QT_DIALOG_FILTER': '1',
        })
        self.assertEqual(status, 0)
        self.assertIn('dialog_filter', events)
        self.assertNotIn('popup_filter', events)
        self.assertFalse(window._v022_fit_ready)

    def test_popup_optin_does_not_enable_dialog_or_fit(self):
        status, events, window, _ = mocked_start({
            'DWM_ENABLE_QT_POPUP_FILTER': '1',
        })
        self.assertEqual(status, 0)
        self.assertNotIn('dialog_filter', events)
        self.assertIn('popup_filter', events)
        self.assertFalse(window._v022_fit_ready)

    def test_autofit_optin_does_not_enable_other_filters(self):
        status, events, window, _ = mocked_start({
            'DWM_ENABLE_QT_BASIC_AUTOFIT': '1',
        })
        self.assertEqual(status, 0)
        self.assertNotIn('dialog_filter', events)
        self.assertNotIn('popup_filter', events)
        self.assertTrue(window._v022_fit_ready)
        self.assertFalse(window.v022_fit_window_button.hidden)

    def test_safe_mode_overrides_optins_in_real_entrypoint(self):
        status, events, window, _ = mocked_start({
            'DWM_SAFE_MODE': '1',
            'DWM_ENABLE_QT_DIALOG_FILTER': '1',
            'DWM_ENABLE_QT_POPUP_FILTER': '1',
            'DWM_ENABLE_QT_BASIC_AUTOFIT': '1',
        })
        self.assertEqual(status, 0)
        self.assertNotIn('dialog_filter', events)
        self.assertNotIn('popup_filter', events)
        self.assertFalse(window._v022_fit_ready)

    def test_diagnostic_boot_marker_states_exact_profile(self):
        status, events, window, log = mocked_start({
            'DWM_CRASH_DIAG': '1',
            'DWM_ENABLE_QT_DIALOG_FILTER': '1',
        })
        self.assertIn('Qt startup profile: STABLE', log)
        self.assertIn('file_dialog_filter=1', log)
        self.assertIn('popup_filter=0', log)
        self.assertIn('basic_auto_fit=0', log)
        self.assertIn('20 Qt event loop returned with code 0', log)

    def test_no_job_runner_or_work_storage_changes_in_startup(self):
        ast.parse(MAIN.read_text(encoding='utf-8'))
        source = MAIN.read_text(encoding='utf-8')
        self.assertIn('DwmWorkbenchAPI()', source)
        self.assertIn('install_integrated_home(window)', source)
        self.assertIn('window.show()', source)
        self.assertIn('application.exec()', source)
        for forbidden in ('save_job_list(', 'run_job(', '.unlink(', '.rmdir(',
                          'shutil.rmtree(', 'settings.reset(', 'config.clear('):
            self.assertNotIn(forbidden, source)

    def test_debug_bat_does_not_overwrite_previous_log(self):
        bat = (ROOT / 'start-debug.bat').read_text(encoding='ascii')
        self.assertIn('Get-Date -Format yyyyMMdd_HHmmss_fff', bat)
        self.assertIn('%RANDOM%.log', bat)
        self.assertIn('dwm-startup-logs', bat)
        self.assertIn('PYTHONFAULTHANDLER=1', bat)
        self.assertIn('PYTHONUNBUFFERED=1', bat)
        self.assertIn('call "%~dp0start.bat"', bat)
        self.assertNotIn('dwm-startup-debug.log', bat)
        self.assertNotIn('.n5jobs', bat)


if __name__ == '__main__':
    unittest.main()
