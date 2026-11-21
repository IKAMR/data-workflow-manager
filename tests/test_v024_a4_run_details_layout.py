"""v0.2.4-a4: read-only Qt run-details sizing and persistence regressions."""
from __future__ import annotations

import ast
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from gui_qt.run_details_layout_v024_a4 import (
    saved_history_widths, history_column_widths,
    content_split_height, plan_table_height, history_table_height,
)

ROOT = Path(__file__).resolve().parents[1]


class LayoutPolicyTests(unittest.TestCase):
    def test_history_defaults_show_all_columns_with_a_flexible_operation(self):
        self.assertEqual(history_column_widths(1120), (165, 590, 110, 135, 110))
        self.assertEqual(history_column_widths(780), (165, 320, 110, 135, 110))

    def test_saved_manual_columns_win_even_on_a_different_window_size(self):
        manual = [186, 420, 95, 160, 140]
        self.assertEqual(history_column_widths(770, json.dumps(manual)), tuple(manual))
        self.assertEqual(history_column_widths(1920, manual), tuple(manual))

    def test_allows_narrow_user_selected_columns(self):
        self.assertEqual(saved_history_widths('[90, 180, 80, 105, 90]'),
                         (90, 180, 80, 105, 90))

    def test_corrupt_or_old_qsettings_does_not_break_opening(self):
        for bad in ('invalid', '{', '[165,320]', '[165,320,110,135,0]',
                    '[165,320,110,135,true]', [100, 200, 300, 400], None):
            with self.subTest(bad=bad):
                self.assertIsNone(saved_history_widths(bad))
                self.assertEqual(history_column_widths(900, bad),
                                 (165, 370, 110, 135, 110))

    def test_full_17_operation_plan_takes_only_rows_needed_not_53_percent(self):
        self.assertEqual(plan_table_height(1200, 17, 22, 28), 414)
        self.assertNotEqual(plan_table_height(1200, 17, 22, 28), int(1200*.53))

    def test_short_window_keeps_lower_panel_readable(self):
        self.assertEqual(plan_table_height(500, 17, 22, 28), 335)
        self.assertEqual(history_table_height(500, 17, 22, 28), 370)
        self.assertEqual(history_table_height(0, 17, 22, 28), 0)
        self.assertGreater(content_split_height(120, 17, 22, 28), 0)


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, fn):
        self.slots.append(fn)

    def emit(self, *args):
        for fn in list(self.slots):
            fn(*args)


class Config:
    def __init__(self, saved=None):
        self.data = dict(saved or {})
        self.sync_count = 0

    def value(self, key):
        return self.data.get(key)

    def setValue(self, key, value):
        self.data[key] = value

    def sync(self):
        self.sync_count += 1


class Header:
    def __init__(self):
        self.widths = [50, 50, 50, 50, 50]
        self.sectionResized = Signal()
        self.modes = {}
        self.stretch = None

    def setStretchLastSection(self, enabled):
        self.stretch = enabled

    def setMinimumSectionSize(self, value):
        self.minimum = value

    def setSectionResizeMode(self, index, mode):
        self.modes[index] = mode

    def resizeSection(self, index, width):
        old = self.widths[index]
        self.widths[index] = width
        self.sectionResized.emit(index, old, width)

    def sectionSize(self, index):
        return self.widths[index]

    def height(self):
        return 28


class Tree:
    def __init__(self, *, rows, viewport=1100, parent=None):
        self.rows = rows
        self.parent = parent
        self.head = Header()
        self.viewport_width = viewport

    def header(self):
        return self.head

    def topLevelItemCount(self):
        return self.rows

    def sizeHintForRow(self, index):
        return 22

    def fontMetrics(self):
        return SimpleNamespace(height=lambda: 16)

    def viewport(self):
        return SimpleNamespace(width=lambda: self.viewport_width)

    def parentWidget(self):
        return self.parent


class Splitter:
    def __init__(self, height=900):
        self.h = height
        self.splitterMoved = Signal()
        self.sizes = []
        self.restore_calls = 0
        self.restored = None

    def height(self):
        return self.h

    def setChildrenCollapsible(self, value):
        self.collapsible = value

    def setHandleWidth(self, value):
        self.handle_width = value

    def setSizes(self, values):
        self.sizes = list(values)

    def saveState(self):
        return tuple(self.sizes)

    def restoreState(self, data):
        self.restore_calls += 1
        if not isinstance(data, (tuple, list)) or len(data) != 2:
            return False
        self.sizes = list(data)
        self.restored = tuple(data)
        return True

    def user_move(self, first):
        self.sizes = [first, self.h-first]
        self.splitterMoved.emit(first, 1)


class Viewer:
    def __init__(self, history_rows=17, plan_rows=17, viewport=1100):
        self.inner = Splitter(820)
        self.history_tree = Tree(rows=history_rows, viewport=viewport, parent=self.inner)
        self.plan = Tree(rows=plan_rows, viewport=viewport)
        self.outer = Splitter(1200)
        self._basic_plan_tree = None
        self._v024_plan_splitter = None


class BaseWindow:
    def __init__(self, config):
        self.config = config
        self._detached_run_window = None
        self.redocks = 0
        self.plan_calls = 0

    def _a9_float_run(self):
        return 'float_result'

    def _basic_add_run_plan(self, viewer):
        self.plan_calls += 1
        viewer._basic_plan_tree = viewer.plan
        viewer._v024_plan_splitter = viewer.outer
        return 'plan_result'

    def _a9_redock_run(self):
        self.redocks += 1
        self._detached_run_window = None
        return 'redock_result'


class RunDetailsUiContract(unittest.TestCase):
    def setUp(self):
        self.timers = []
        core = ModuleType('PySide6.QtCore')
        core.QTimer = SimpleNamespace(singleShot=lambda ms, fn: self.timers.append((ms, fn)))
        widgets = ModuleType('PySide6.QtWidgets')
        widgets.QSplitter = Splitter
        widgets.QHeaderView = SimpleNamespace(ResizeMode=SimpleNamespace(Interactive=11))
        parent = ModuleType('gui_qt.main_v024_a3')
        parent.DwmMainWindow = BaseWindow
        self.patcher = patch.dict(sys.modules, {
            'PySide6': ModuleType('PySide6'),
            'PySide6.QtCore': core,
            'PySide6.QtWidgets': widgets,
            'gui_qt.main_v024_a3': parent,
        })
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        path = ROOT / 'gui_qt/main_v024_a4.py'
        spec = spec_from_file_location('_dwm_v024_a4_gui_under_test', path)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        self.Window = module.DwmMainWindow
        self.cols_key = module._COL_KEY
        self.inner_key = module._INNER_KEY
        self.outer_key = module._OUTER_KEY
        self.config = Config()
        self.win = self.Window(self.config)

    def flush(self):
        # Calls are queued once, not by repeated app-wide timer activity.
        for _i in range(10):
            if not self.timers:
                break
            queue, self.timers = self.timers, []
            for delay, fn in queue:
                self.assertIn(delay, (0, 25))
                fn()
        self.assertFalse(self.timers)

    def open_viewer(self, viewer=None):
        viewer = viewer or Viewer()
        self.win._detached_run_window = viewer
        self.assertEqual(self.win._a9_float_run(), 'float_result')
        self.assertEqual(self.win._basic_add_run_plan(viewer), 'plan_result')
        self.flush()
        return viewer

    def test_defaults_fit_17_rows_and_make_columns_interactive(self):
        viewer = self.open_viewer()
        self.assertEqual(viewer.outer.sizes, [414, 786])
        self.assertEqual(viewer.history_tree.header().widths,
                         [165, 570, 110, 135, 110])
        self.assertEqual(set(viewer.history_tree.header().modes.values()), {11})
        self.assertFalse(viewer.history_tree.header().stretch)
        self.assertEqual(viewer.inner.sizes, [414, 406])
        self.assertFalse(viewer.inner.collapsible)
        self.assertEqual(viewer.inner.handle_width, 9)
        self.assertNotIn(self.cols_key, self.config.data,
                         'automatic first layout must not be stored as a user edit')

    def test_user_columns_and_inner_splitter_survive_next_job_and_reopen(self):
        first = self.open_viewer()
        first.history_tree.header().resizeSection(1, 440)
        self.assertEqual(json.loads(self.config.data[self.cols_key]),
                         [165, 440, 110, 135, 110])
        first.inner.user_move(390)
        self.assertEqual(self.config.data[self.inner_key], (390, 430))
        self.assertEqual(self.win._a9_redock_run(), 'redock_result')
        self.assertEqual(self.config.sync_count, 1)
        second = self.open_viewer(Viewer(viewport=770))
        self.assertEqual(second.history_tree.header().widths,
                         [165, 440, 110, 135, 110])
        self.assertEqual(second.inner.restored, (390, 430))
        self.assertEqual(self.win.redocks, 1)

    def test_existing_outer_a1_preference_wins(self):
        self.config.data[self.outer_key] = (500, 700)
        v = self.open_viewer()
        self.assertEqual(v.outer.sizes, [], 'a1 owns restoration of this splitter')
        self.assertEqual(v.inner.sizes, [414, 406])

    def test_unexpected_history_parent_does_not_attach_or_crash(self):
        v = Viewer()
        v.history_tree.parent = object()
        self.win._detached_run_window = v
        self.win._a9_float_run()
        self.flush()
        self.assertFalse(getattr(v, '_v024_a4_bound', False))

    def test_queued_layout_ignores_closed_native_viewer(self):
        v = Viewer()
        self.win._detached_run_window = v
        self.win._a9_float_run()
        self.win._basic_add_run_plan(v)
        # Simulate a QWidget destroyed before a delayed initial sizing pass.
        v.outer.height = lambda: (_ for _ in ()).throw(RuntimeError('deleted'))
        self.flush()
        self.assertEqual(self.win.plan_calls, 1)

    def test_redock_without_viewer_is_safe(self):
        self.assertEqual(self.win._a9_redock_run(), 'redock_result')
        self.assertEqual(self.config.sync_count, 0)


class SafeIntegrationStaticTests(unittest.TestCase):
    def test_a4_entrypoint_retains_a3_and_original_workbench(self):
        main = (ROOT / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        self.assertIn('from gui_qt.main_v024_a3 import DwmMainWindow as _A3Window', main)
        self.assertIn('from gui_qt.main_v024_a4 import DwmMainWindow as _A4Window', main)
        self.assertIn('DwmMainWindow = _A4Window', main)
        self.assertIn('DwmWorkbenchAPI = _A3WorkbenchAPI', main)
        self.assertLess(main.index('from gui_qt.main_v024_a3'),
                        main.index('from gui_qt.main_v024_a4'))

    def test_no_work_source_or_runner_mutations(self):
        path = ROOT / 'gui_qt/main_v024_a4.py'
        source = path.read_text('utf-8')
        for forbidden in ('run_job(', 'save_job_list(', '_persist_updated_job(',
                          'job.reset_execution(', '.unlink(', '.rmdir('):
            self.assertNotIn(forbidden, source)
        for node in ast.parse(source).body:
            if isinstance(node, ast.ImportFrom):
                self.assertFalse((node.module or '').startswith('PySide6'))
        self.assertIn("_OUTER_KEY = 'qt/v024/basic_details_vertical_splitter'", source)

    def test_version_and_distribution_match(self):
        from re import search
        version = (ROOT / 'version.py').read_text('utf-8')
        project = (ROOT / 'pyproject.toml').read_text('utf-8')
        spec = spec_from_file_location('_dwm_a4_version_rule',
                                       ROOT / 'tests/version_assertions.py')
        rule = module_from_spec(spec)
        spec.loader.exec_module(rule)
        rule.assert_release_at_least(self, version, '0.2.4', 4)
        declaration = search(r'(?m)^VERSION\s*=\s*"([^"]+)"', version)
        self.assertIsNotNone(declaration)
        self.assertIn('version = "' + declaration.group(1).replace('-a', 'a') + '"', project)


if __name__ == '__main__':
    unittest.main()
