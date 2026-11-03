"""DWM a9 Windows floating dock safety regressions (headless)."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'gui_qt' / 'main_window.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)
MAIN = next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == 'DwmMainWindow')


def extract_method(name):
    member = next(node for node in MAIN.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return member


class QTimerFake:
    pending = []

    @classmethod
    def singleShot(cls, delay, callback):
        assert delay == 0
        cls.pending.append(callback)


class FakeDock:
    def __init__(self, floating=True):
        self.floating = floating
        self.size = (200, 250)

    def isFloating(self):
        return self.floating

    def setFloating(self, value):
        self.floating = value

    def width(self):
        return self.size[0]

    def height(self):
        return self.size[1]

    def resize(self, w, h):
        self.size = (w, h)


methods = [extract_method(name) for name in ('_a8_dock_floating', '_a8_finish_floating', '_a9_correct_native_float')]
namespace = {'QTimer': QTimerFake}
exec(compile(ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[])), '<dock-test>', 'exec'), namespace)


class Harness:
    _a8_dock_floating = namespace['_a8_dock_floating']
    _a8_finish_floating = namespace['_a8_finish_floating']
    _a9_correct_native_float = namespace['_a9_correct_native_float']

    def __init__(self):
        self.dock_log = FakeDock()
        self.dock_run = FakeDock()
        self.dock_system = FakeDock()
        self._detached_log_window = None
        self._detached_run_window = None
        self.log_openings = 0
        self.run_openings = 0
        self._a8_floating_once = set()
        self.recover_calls = 0
        self.button_calls = 0

    def _recover_windows(self):
        self.recover_calls += 1

    def _a8_update_log_window_buttons(self):
        self.button_calls += 1

    def _a8_float_job_log(self):
        self.log_openings += 1

    def _a9_float_run(self):
        self.run_openings += 1


class DockSafetyTests(unittest.TestCase):
    def setUp(self):
        QTimerFake.pending.clear()
        self.window = Harness()

    def test_docks_are_individually_movable_but_no_floating_tab_groups(self):
        self.assertIn('QMainWindow.DockOption.AllowNestedDocks', SOURCE)
        self.assertNotIn('QMainWindow.DockOption.GroupedDragging', SOURCE)
        self.assertNotIn('QMainWindow.DockOption.AllowTabbedDocks', SOURCE)
        self.assertNotIn('tabifyDockWidget(', SOURCE)
        self.assertIn('DockWidgetFeature.DockWidgetFloatable', SOURCE)
        self.assertIn('DockWidgetFeature.DockWidgetMovable', SOURCE)

    def test_native_log_float_is_corrected_and_opens_normal_viewer(self):
        self.window._a8_dock_floating('log', True)
        self.assertEqual(len(QTimerFake.pending), 1)
        self.assertEqual(self.window.log_openings, 0)
        QTimerFake.pending.pop()()
        self.assertFalse(self.window.dock_log.isFloating())
        self.assertEqual(self.window.log_openings, 1)
        self.assertEqual(self.window.dock_log.size, (200, 250))

    def test_docked_again_before_event_loop_runs_does_not_open_viewer(self):
        self.window._a8_dock_floating('run', True)
        self.window.dock_run.floating = False
        QTimerFake.pending.pop()()
        self.assertEqual(self.window.run_openings, 0)
        self.assertEqual(self.window.dock_run.size, (200, 250))

    def test_native_run_float_is_corrected_and_opens_normal_viewer(self):
        self.window._a8_dock_floating('run', True)
        QTimerFake.pending.pop()()
        self.assertFalse(self.window.dock_run.isFloating())
        self.assertEqual(self.window.run_openings, 1)

    def test_other_panel_native_floating_still_uses_deferred_geometry(self):
        self.window._a8_dock_floating('system', True)
        self.assertEqual(self.window.recover_calls, 0)
        self.assertEqual(len(QTimerFake.pending), 1)
        QTimerFake.pending.pop()()
        self.assertEqual(self.window.recover_calls, 1)
        self.assertEqual(self.window.dock_system.size, (940, 540))

    def test_returning_to_main_window_does_not_change_geometry(self):
        self.window._a8_dock_floating('log', False)
        self.assertEqual(self.window.recover_calls, 0)
        self.assertEqual(QTimerFake.pending, [])

    def test_old_tabbed_native_layouts_not_restored(self):
        self.assertIn('saveState(4)', SOURCE)
        self.assertIn('restoreState(state, 4)', SOURCE)
        self.assertNotIn('saveState(3)', SOURCE)
        self.assertNotIn('restoreState(state, 3)', SOURCE)


if __name__ == '__main__':
    unittest.main()
