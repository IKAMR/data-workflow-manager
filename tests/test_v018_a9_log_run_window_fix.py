"""a9: Kjøreløp and Kjørelogg are distinct, safely detachable views.

Source-level and actual-method tests run without PySide6 on build machines;
final Win32 drag/Z-order validation still belongs in the user test cycle.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
GUI = (ROOT / 'gui_qt' / 'main_window.py').read_text(encoding='utf-8')
VIEW = (ROOT / 'gui_qt' / 'detached_log_window_v018_a9.py').read_text(encoding='utf-8')
cls = next(n for n in ast.parse(GUI).body if isinstance(n, ast.ClassDef) and n.name == 'DwmMainWindow')


def method(*names):
    definitions = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(definitions) == len(names), names
    ns = {'DetachedRunWindow': FakeRunWindow, 'STYLE': 'dark'}
    exec(compile(ast.fix_missing_locations(ast.Module(body=definitions, type_ignores=[])), '<gui>', 'exec'), ns)
    return ns


class Signal:
    def __init__(self): self.subscribers = []
    def connect(self, handler): self.subscribers.append(handler)
    def emit(self):
        for item in self.subscribers: item()


class FakeRunWindow:
    def __init__(self):
        self.redockRequested = Signal()
        self.visible = False
        self.deleted = False
        self.saved = 'run-geometry'
        self.data = None

    def setStyleSheet(self, theme): self.theme = theme
    def set_run_data(self, summary, percent, events): self.data = (summary, percent, events)
    def show(self): self.visible = True
    def hide(self): self.visible = False
    def raise_(self): pass
    def activateWindow(self): pass
    def saveGeometry(self): return self.saved
    def restoreGeometry(self, value): self.restored = value
    def deleteLater(self): self.deleted = True


class FakeAction:
    def __init__(self): self.enabled = True; self.text = ''
    def setEnabled(self, enabled): self.enabled = enabled
    def setText(self, text): self.text = text


class FakeDock:
    def __init__(self): self.visible = True; self.native_float = False; self.action = FakeAction()
    def toggleViewAction(self): return self.action
    def hide(self): self.visible = False
    def show(self): self.visible = True
    def raise_(self): pass
    def isFloating(self): return self.native_float
    def setFloating(self, value): self.native_float = value


class FakeConfig:
    def __init__(self): self.values = {}
    def value(self, key): return self.values.get(key)
    def setValue(self, key, value): self.values[key] = value


methods = method('_a9_float_run', '_a9_redock_run', '_a9_sync_detached_run',
                 '_a9_update_run_window_buttons')


class FakeMain:
    _a9_float_run = methods['_a9_float_run']
    _a9_redock_run = methods['_a9_redock_run']
    _a9_sync_detached_run = methods['_a9_sync_detached_run']
    _a9_update_run_window_buttons = methods['_a9_update_run_window_buttons']

    def __init__(self):
        self._detached_run_window = None
        self.dock_run = FakeDock()
        self.run_window_button = FakeAction()
        self.float_run_action = FakeAction()
        self.run_summary = SimpleNamespace(text=lambda: 'JOB-001 Klar – 0/9')
        self.run_progress_bar = SimpleNamespace(value=lambda: 0)
        self.run_events = SimpleNamespace(toPlainText=lambda: '9 deljobber, ingen kjørt')
        self.config = FakeConfig()
        self.recoveries = 0

    def _a9_recover_detached_run_geometry(self): self.recoveries += 1


class WindowSeparationTests(unittest.TestCase):
    def test_normal_windows_are_distinct_and_never_tool_windows(self):
        self.assertIn('self.setWindowTitle("Kjøreløp – Data Workflow Manager")', VIEW)
        self.assertIn('self.setWindowTitle("Kjørelogg – Data Workflow Manager")', VIEW)
        self.assertEqual(VIEW.count('super().__init__(None, Qt.WindowType.Window)'), 2)
        self.assertNotIn('Qt.WindowStaysOnTopHint', VIEW)
        self.assertNotIn('Qt.WindowType.Tool', VIEW)

    def test_native_drag_is_replaced_by_custom_explicit_detach(self):
        self.assertIn('dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)', GUI)
        self.assertIn('dock.setTitleBarWidget(header)', GUI)
        self.assertIn('header.detachRequested.connect(', GUI)
        self.assertIn('self.drag_label.detached.connect(self.detachRequested.emit)', VIEW)
        self.assertIn('self.detached.emit()', VIEW)
        self.assertNotIn('QMainWindow.DockOption.GroupedDragging', GUI)

    def test_run_viewer_opens_as_a_second_window_not_a_floating_qdock(self):
        ui = FakeMain()
        ui._a9_float_run()
        viewer = ui._detached_run_window
        self.assertIsInstance(viewer, FakeRunWindow)
        self.assertTrue(viewer.visible)
        self.assertFalse(ui.dock_run.visible)
        self.assertFalse(ui.dock_run.action.enabled)
        self.assertFalse(ui.dock_run.native_float)
        self.assertEqual(ui.run_window_button.text, 'Fest til hovedvindu')
        self.assertEqual(viewer.data, ('JOB-001 Klar – 0/9', 0, '9 deljobber, ingen kjørt'))
        self.assertEqual(ui.recoveries, 1)

    def test_run_viewer_mirrors_status_and_redocks_without_duplicate(self):
        ui = FakeMain()
        ui._a9_float_run()
        viewer = ui._detached_run_window
        ui.run_summary = SimpleNamespace(text=lambda: 'JOB-002 Ferdig – 9/9')
        ui.run_progress_bar = SimpleNamespace(value=lambda: 100)
        ui.run_events = SimpleNamespace(toPlainText=lambda: '9 deljobber OK')
        ui._a9_sync_detached_run()
        self.assertEqual(viewer.data, ('JOB-002 Ferdig – 9/9', 100, '9 deljobber OK'))
        viewer.redockRequested.emit()
        self.assertIsNone(ui._detached_run_window)
        self.assertFalse(viewer.visible)
        self.assertTrue(viewer.deleted)
        self.assertTrue(ui.dock_run.visible)
        self.assertTrue(ui.dock_run.action.enabled)
        self.assertEqual(ui.config.values['qt/a9_independent_run_geometry'], 'run-geometry')
        ui._a9_float_run()
        self.assertIsNot(ui._detached_run_window, viewer)
        self.assertEqual(ui.run_window_button.text, 'Fest til hovedvindu')

    def test_log_has_no_saved_status_option_after_new_real_run(self):
        from test_v018_a8_log_fix import FakeWindow
        ui = FakeWindow()
        ui._active_id = 'JOB-001'
        ui._a8_refresh_job_log(force=True)
        self.assertIn('Ingen faktisk kjørelogg', ui.job_log_text.value)
        self.assertEqual(ui.job_run_combo.findData('__snapshot__'), -1)
        run = SimpleNamespace(run_id='log-actual-01', status='running', started_at='2026-11-03T23:00:00')
        ui.api.logs['JOB-001'] = [run]
        ui._a8_refresh_job_log(force=True)
        self.assertEqual(ui.job_run_combo.currentData(), 'log-actual-01')
        self.assertIn('log-actual-01', ui.job_log_text.value)
        self.assertNotIn('Lagret jobbstatus', ui.job_log_text.value)

    def test_saved_status_remains_in_kjorelop(self):
        from test_v018_a8_log_fix import FakeWindow
        ui = FakeWindow()
        ui._a8_restore_run_context(force=True)
        self.assertIn('Lagret jobbstatus', ui.run_events.value)
        self.assertIn('JOB-001', ui.run_summary.value)


if __name__ == '__main__':
    unittest.main()
