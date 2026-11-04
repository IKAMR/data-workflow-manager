"""a12: compact job controls and preserve a readable job row after Qt layout restore.

Qt-independent unit checks; verify actual Windows/PySide6 geometry separately.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / 'gui_qt' / 'main_window.py').read_text(encoding='utf-8')
CLASS = next(n for n in ast.parse(SRC).body if isinstance(n, ast.ClassDef) and n.name == 'DwmMainWindow')
METHODS = ('_a12_toggle_job_rule', '_a12_balance_left_docks', '_a12_repair_cramped_job_panel')
NODES = [n for n in CLASS.body if isinstance(n, ast.FunctionDef) and n.name in METHODS]


class FakeTimer:
    pending = []

    @classmethod
    def singleShot(cls, delay, action):
        assert delay == 0
        cls.pending.append(action)

    @classmethod
    def flush(cls):
        while cls.pending:
            cls.pending.pop(0)()


Qt = SimpleNamespace(Orientation=SimpleNamespace(Vertical='vertical'),
                     DockWidgetArea=SimpleNamespace(LeftDockWidgetArea='left'))
ns = {'Qt': Qt, 'QTimer': FakeTimer}
exec(compile(ast.fix_missing_locations(ast.Module(body=NODES, type_ignores=[])),
             '<compact-jobs>', 'exec'), ns)


class FakeDock:
    def __init__(self, height=280, *, visible=True, floating=False, area='left'):
        self._height = height
        self._visible = visible
        self._floating = floating
        self.area = area

    def height(self): return self._height
    def isVisible(self): return self._visible
    def isFloating(self): return self._floating


class FakeWidget:
    def __init__(self): self.visible = False; self.label = ''
    def setVisible(self, state): self.visible = state
    def setText(self, value): self.label = value


class FakeViewport:
    def __init__(self, height): self._height = height
    def height(self): return self._height


class FakeTree:
    def __init__(self, height): self._viewport = FakeViewport(height)
    def viewport(self): return self._viewport


class FakeSettings:
    def __init__(self): self.values = {}
    def setValue(self, key, value): self.values[key] = value


class FakeWindow:
    _a12_toggle_job_rule = ns['_a12_toggle_job_rule']
    _a12_balance_left_docks = ns['_a12_balance_left_docks']
    _a12_repair_cramped_job_panel = ns['_a12_repair_cramped_job_panel']

    def __init__(self):
        self._a12_job_rule_visible = False
        self.job_rule_box = FakeWidget()
        self.job_rule_toggle = FakeWidget()
        self.config = FakeSettings()
        self.dock_jobs = FakeDock(270)
        self.dock_workflow = FakeDock(260)
        self.jobs_tree = FakeTree(10)
        self.sizes = []

    def dockWidgetArea(self, dock): return dock.area
    def resizeDocks(self, docks, sizes, direction):
        self.sizes.append((docks, sizes, direction))


class CompactJobPanelTests(unittest.TestCase):
    def setUp(self):
        FakeTimer.pending.clear()
        self.w = FakeWindow()

    def test_rule_editor_collapsed_but_original_controls_retained(self):
        self.assertIn('self.job_rule_box.setVisible(self._a12_job_rule_visible)', SRC)
        self.assertIn('"qt/a12_job_rule_visible", False, type=bool', SRC)
        self.assertIn('self.job_output_rule = QLineEdit()', SRC)
        self.assertIn('self.job_rule_apply = QPushButton("Bruk regel")', SRC)
        self.assertIn('self.job_rule_preview = _muted(', SRC)
        self.assertIn('self.job_rule_toggle = QPushButton("Regel ▸")', SRC)

    def test_job_and_workflow_tables_enforce_useful_minimum_height(self):
        self.assertIn('self.jobs_tree.setMinimumHeight(110)', SRC)
        self.assertIn('self.workflow_tree.setMinimumHeight(192)', SRC)
        self.assertIn('self.dock_jobs.setMinimumWidth(320)', SRC)
        self.assertIn('self.dock_workflow.setMinimumWidth(320)', SRC)

    def test_toggle_is_only_presentation_and_records_preference(self):
        self.w._a12_toggle_job_rule()
        self.assertTrue(self.w.job_rule_box.visible)
        self.assertEqual(self.w.job_rule_toggle.label, 'Regel ▾')
        self.assertTrue(self.w.config.values['qt/a12_job_rule_visible'])
        FakeTimer.flush()
        self.assertEqual(len(self.w.sizes), 1)
        self.w._a12_toggle_job_rule()
        self.assertFalse(self.w.job_rule_box.visible)
        self.assertEqual(self.w.job_rule_toggle.label, 'Regel ▸')
        self.assertFalse(self.w.config.values['qt/a12_job_rule_visible'])

    def test_stored_layout_with_hidden_job_rows_is_repaired(self):
        self.w._a12_repair_cramped_job_panel()
        self.assertEqual(len(self.w.sizes), 1)
        docks, sizes, axis = self.w.sizes[0]
        self.assertEqual(docks, [self.w.dock_jobs, self.w.dock_workflow])
        self.assertLess(sizes[0], sizes[1])
        self.assertEqual(axis, 'vertical')

    def test_healthy_job_panel_remains_unchanged(self):
        self.w.jobs_tree._viewport._height = 130
        self.w._a12_repair_cramped_job_panel()
        self.assertEqual(self.w.sizes, [])

    def test_non_left_dock_or_detached_panel_is_not_repositioned(self):
        self.w.dock_workflow.area = 'bottom'
        self.w._a12_balance_left_docks()
        self.assertEqual(self.w.sizes, [])
        self.w.dock_workflow.area = 'left'
        self.w.dock_workflow._floating = True
        self.w._a12_balance_left_docks()
        self.assertEqual(self.w.sizes, [])

    def test_default_reset_and_old_state_have_repair_hooks(self):
        self.assertIn('QTimer.singleShot(0, self._a12_balance_left_docks)', SRC)
        self.assertIn('QTimer.singleShot(0, self._a12_repair_cramped_job_panel)', SRC)
        self.assertNotIn('tabifyDockWidget(', SRC)
        self.assertNotIn('QMainWindow.DockOption.AllowTabbedDocks', SRC)

    def test_run_dock_balance_includes_left_and_bottom_areas(self):
        self.assertIn('[self.dock_jobs, self.dock_workflow], [350, 350]', SRC)
        self.assertIn('self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)', SRC)
        self.assertIn('self.dockWidgetArea(self.dock_jobs) == Qt.DockWidgetArea.LeftDockWidgetArea', SRC)


if __name__ == '__main__':
    unittest.main()
