"""Headless contracts for an independent, normally stacked job-log window.

The Qt tool dock remains for in-window docking, while the standalone viewer
must be a true unparented Qt.Window, not a floating Qt.Tool/QDockWidget.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'gui_qt' / 'main_window.py').read_text(encoding='utf-8')
VIEWER = (ROOT / 'gui_qt' / 'detached_log_window_v018_a9.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)
AST_VIEWER = ast.parse(VIEWER)
CLASS = next(x for x in TREE.body if isinstance(x, ast.ClassDef) and x.name == 'DwmMainWindow')


def method(*names):
    funcs = [x for x in CLASS.body if isinstance(x, ast.FunctionDef) and x.name in names]
    assert len(funcs) == len(names), names
    namespace = {'DetachedJobLogWindow': FakeDetached, 'STYLE': 'theme'}
    exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])), 'gui_qt/main_window.py', 'exec'), namespace)
    return namespace


class Signal:
    def __init__(self): self.handlers = []
    def connect(self, callback): self.handlers.append(callback)
    def emit(self, *args):
        for callback in self.handlers: callback(*args)


class FakeDetached:
    def __init__(self):
        self.redockRequested = Signal()
        self.runSelected = Signal()
        self.refreshRequested = Signal()
        self.followChanged = Signal()
        self.style = None
        self.shown = False
        self.deleted = False
        self.text = ''
        self.follow = False
        self.rows = []
        self.selected = None
        self.raise_count = 0

    def setStyleSheet(self, value): self.style = value
    def set_runs(self, rows, selected): self.rows, self.selected = rows, selected
    def set_follow(self, enabled): self.follow = enabled
    def set_log_text(self, content): self.text = content
    def show(self): self.shown = True
    def hide(self): self.shown = False
    def raise_(self): self.raise_count += 1
    def activateWindow(self): pass
    def deleteLater(self): self.deleted = True
    def saveGeometry(self): return 'geometry'
    def restoreGeometry(self, geometry): pass


class FakeDock:
    def __init__(self): self.shown = True; self.float_calls = 0; self.action=SimpleNamespace(setEnabled=lambda enabled: None)
    def toggleViewAction(self):return self.action
    def hide(self): self.shown = False
    def show(self): self.shown = True
    def raise_(self): pass
    def setFloating(self, floating): self.float_calls += 1


class FakeConfig:
    def __init__(self): self.values={}
    def value(self, key): return self.values.get(key)
    def setValue(self, key, value): self.values[key]=value


class FakeCombo:
    def __init__(self): self.rows=[('Arbeidsflyt','run-01'),('Lagret jobbstatus','__snapshot__')];self.idx=0
    def count(self): return len(self.rows)
    def itemText(self, i):return self.rows[i][0]
    def itemData(self, i):return self.rows[i][1]
    def currentData(self):return self.rows[self.idx][1]
    def currentIndex(self):return self.idx
    def findData(self, value):return next((i for i, row in enumerate(self.rows) if row[1]==value), -1)
    def setCurrentIndex(self, idx):self.idx=idx


class FakeLabel:
    def __init__(self):self.text=''
    def setText(self, text):self.text=text


class FakeFollow:
    def __init__(self):self.checked=True
    def isChecked(self):return self.checked
    def setChecked(self, value):self.checked=value


class FakeLog:
    def toPlainText(self):return 'START: Metadataoversikt\nOK: Ferdig'


NAMES = ('_a8_float_job_log', '_a8_update_log_window_buttons',
         '_a9_redock_job_log', '_a9_sync_detached_log_choices',
         '_a9_sync_detached_log_follow', '_a9_sync_detached_log_text',
         '_a9_detached_run_selected')
METHODS = method(*NAMES)


class FakeMain:
    def __init__(self):
        self.config=FakeConfig();self.dock_log=FakeDock()
        self.job_log_text=FakeLog()
        self.log_follow=FakeFollow()
        self.job_run_combo=FakeCombo()
        self.log_window_button=FakeLabel()
        self.float_job_log_action=FakeLabel()
        self._detached_log_window=None
        self.refreshed=0
        self.recovered=0
        self.shown_run=0

    def _a8_refresh_job_log(self, **kwargs):self.refreshed+=1
    def _a8_show_selected_run(self):self.shown_run+=1
    def _a9_recover_detached_log_geometry(self):self.recovered+=1


for name, fn in METHODS.items():
    setattr(FakeMain, name, fn)


class NormalLogTests(unittest.TestCase):
    def test_window_is_unparented_normal_window(self):
        self.assertIn('super().__init__(None, Qt.WindowType.Window)', VIEWER)
        self.assertNotIn('Qt.WindowType.Tool', VIEWER)
        self.assertNotIn('Qt.WindowStaysOnTopHint', VIEWER)
        self.assertIn('DockWidgetFloatable', SOURCE)
        self.assertIn('if name in {"log", "run"}:', SOURCE)
        self.assertIn('dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)', SOURCE)
        self.assertIn('DetachableDockTitleBar(title)', SOURCE)
        self.assertFalse(any('setWindowFlags(' in m for m in (SOURCE, VIEWER)))

    def test_independent_viewer_toggles_without_qdockwidget_floating(self):
        ui = FakeMain()
        ui._a8_float_job_log()
        window = ui._detached_log_window
        self.assertIsInstance(window, FakeDetached)
        self.assertFalse(ui.dock_log.shown)
        self.assertTrue(window.shown)
        self.assertEqual(window.text, 'START: Metadataoversikt\nOK: Ferdig')
        self.assertEqual(ui.dock_log.float_calls, 0)
        self.assertEqual(ui.log_window_button.text, 'Fest til hovedvindu')
        self.assertEqual(window.rows[0], ('Arbeidsflyt','run-01'))
        ui._a8_float_job_log()
        self.assertIsNone(ui._detached_log_window)
        self.assertTrue(ui.dock_log.shown)
        self.assertTrue(window.deleted)
        self.assertEqual(ui.log_window_button.text, 'Eget vindu')
        self.assertEqual(ui.dock_log.float_calls, 0)

    def test_viewer_close_docks_and_saves_geometry(self):
        ui=FakeMain()
        ui._a8_float_job_log()
        window=ui._detached_log_window
        window.redockRequested.emit()
        self.assertIsNone(ui._detached_log_window)
        self.assertEqual(ui.config.values['qt/a9_independent_log_geometry'],'geometry')
        self.assertTrue(ui.dock_log.shown)

    def test_live_content_selection_and_follow_use_same_source(self):
        ui=FakeMain()
        ui._a8_float_job_log()
        window=ui._detached_log_window
        ui._a9_detached_run_selected('__snapshot__')
        self.assertEqual(ui.job_run_combo.currentData(),'__snapshot__')
        self.assertEqual(ui.shown_run,0)  # Qt's actual currentIndexChanged signal displays it.
        ui.log_follow.setChecked(False)
        ui._a9_sync_detached_log_follow()
        self.assertFalse(window.follow)
        window.followChanged.emit(True)
        self.assertTrue(ui.log_follow.isChecked())
        window.refreshRequested.emit()
        self.assertEqual(ui.refreshed,2)

    def test_layout_change_keeps_detached_log_single_view(self):
        self.assertIn('if self._detached_log_window is not None:\n            self.dock_log.hide()', SOURCE)
        self.assertIn('self.dock_log.toggleViewAction().setEnabled(False)', SOURCE)
        self.assertIn('self.dock_log.toggleViewAction().setEnabled(True)', SOURCE)

    def test_normal_window_not_duplicated_when_toggled(self):
        ui=FakeMain()
        ui._a8_float_job_log()
        first=ui._detached_log_window
        ui._a8_float_job_log()
        ui._a8_float_job_log()
        self.assertIsNot(ui._detached_log_window, first)
        self.assertTrue(first.deleted)
        self.assertEqual(ui.dock_log.float_calls,0)


if __name__ == '__main__': unittest.main()
