"""Qt-free guards for the Basic/Advanced screen boundary and run delegation."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
QT = ROOT / 'gui_qt' / 'basic_main_v0111_a1.py'
START = ROOT / 'gui_qt' / '__main__.py'
MAIN = ROOT / 'gui_qt' / 'main_window.py'


class BasicWiringTests(unittest.TestCase):
    def test_startup_uses_basic_wrapper_of_existing_workbench(self):
        entry = START.read_text('utf-8')
        basic = QT.read_text('utf-8')
        ast.parse(entry)
        ast.parse(basic)
        self.assertIn('from gui_qt.basic_main_v0111_a1 import DwmMainWindow', entry)
        self.assertIn('window = DwmMainWindow(api)', entry)
        self.assertIn('class DwmMainWindow(_AdvancedMainWindow):', basic)
        self.assertIn('from .main_window import DOCK_NAMES, DwmMainWindow as _AdvancedMainWindow', basic)
        self.assertIn('from app.workbench_api_v0111_a2 import DwmWorkbenchAPI', entry)

    def test_simple_front_end_has_only_source_work_start_and_result_actions(self):
        source = QT.read_text('utf-8')
        for label in ('Finn uttrekk…', 'Velg Work…', 'Start kontroll',
                      'Se resultatvisninger…', 'Avansert modus'):
            self.assertIn(label, source)
        self.assertIn('self._run_selected()', source)
        self.assertIn('self._continue_job()', source)
        self.assertIn('self._a12_open_result_center()', source)
        self.assertIn('self._request_stop', source)
        self.assertIn("self.pages.addTab(area, 'Enkel start')", source)
        self.assertNotIn("self.pages.insertTab(0, area", source)
        self.assertNotIn('mkdir(', source)
        self.assertNotIn('copytree(', source)
        self.assertIn('Work brukes direkte:', source)

    def test_advanced_docks_survive_basic_and_close(self):
        source = QT.read_text('utf-8')
        self.assertIn('self._basic_advanced_state = self.saveState(4)', source)
        self.assertIn("getattr(self, 'dock_' + name).hide()", source)
        self.assertIn('self._toolbar.hide()', source)
        self.assertIn("if getattr(self, '_basic_active', False):", source)
        self.assertIn('self._toolbar.show()', source)
        self.assertIn('self.restoreState(self._basic_advanced_state, 4)', source)
        self.assertIn("self.config.setValue('qt/window_state', advanced_state)", source)
        self.assertIn('if event.isAccepted() and advanced_state is not None:', source)
        self.assertIn("self.config.setValue('qt/v0111_interface_mode', 'advanced')", source)
        self.assertIn("self.config.setValue('qt/v0111_interface_mode', 'basic')", source)

    def test_original_advanced_workbench_is_not_modified(self):
        if MAIN.exists():
            original = MAIN.read_text('utf-8')
            self.assertIn('def _review_preflight(', original)
            self.assertIn('def _run_selected(', original)
            self.assertIn('def _a12_open_result_center(', original)


if __name__ == '__main__':
    unittest.main()


class NativeStateBehaviorTests(unittest.TestCase):
    """Execute the actual mode methods with Qt-free stand-ins."""

    def setUp(self):
        tree = ast.parse(QT.read_text('utf-8'))
        real_class = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                          and node.name == 'DwmMainWindow')
        names = {'_enter_basic', '_leave_basic', 'closeEvent'}
        methods = [node for node in real_class.body if isinstance(node, ast.FunctionDef)
                   and node.name in names]

        class Node:
            def __init__(self): self.visible = True
            def hide(self): self.visible = False
            def show(self): self.visible = True
        class Pages:
            def __init__(self):
                self.advanced = object()
                self.basic = object()
                self.current = self.advanced
                self.tabs = Node()
            def currentWidget(self): return self.current
            def setCurrentWidget(self, widget): self.current = widget
            def setCurrentIndex(self, index): self.current = self.advanced
            def tabBar(self): return self.tabs
        class Config:
            def __init__(self): self.values = {}
            def setValue(self, key, value): self.values[key] = value
            def sync(self): pass
        class Base:
            def saveState(self, _version):
                return 'ADVANCED' if self._toolbar.visible else 'BASIC_HIDDEN'
            def restoreState(self, state, version):
                self.restored_state = (state, version)
                self.dock_jobs.show()
            def closeEvent(self, event):
                if event.isAccepted():
                    self.config.setValue('qt/window_state', self.saveState(4))

        klass = ast.ClassDef(name='DwmMainWindow', bases=[ast.Name(id='Base', ctx=ast.Load())],
                             keywords=[], body=methods, decorator_list=[])
        module = ast.fix_missing_locations(ast.Module(body=[klass], type_ignores=[]))
        namespace = {'Base': Base, 'DOCK_NAMES': ('jobs', 'workflow')}
        exec(compile(module, str(QT), 'exec'), namespace)
        self.Window, self.Node, self.Pages, self.Config = (
            namespace['DwmMainWindow'], Node, Pages, Config,
        )

    def window(self):
        w = self.Window()
        w.pages = self.Pages()
        w._basic_page = w.pages.basic
        w._basic_advanced_page = w.pages.advanced
        w._basic_active = False
        w._basic_selection_edited = True
        w._basic_advanced_state = None
        w._toolbar = self.Node()
        w.dock_jobs = self.Node()
        w.dock_workflow = self.Node()
        w._menu = self.Node()
        w._status = self.Node()
        w.menuBar = lambda: w._menu
        w.statusBar = lambda: w._status
        w.config = self.Config()
        w._load_basic_active_job = lambda: None
        w._sync_basic_status = lambda: None
        w._refresh = lambda **kwargs: None
        return w

    def test_switch_keeps_same_native_docks_and_returns_to_advanced_page(self):
        w = self.window()
        original_dock = w.dock_jobs
        w._enter_basic()
        self.assertEqual(w._basic_advanced_state, 'ADVANCED')
        self.assertTrue(w._basic_active)
        self.assertIs(w.pages.current, w.pages.basic)
        self.assertFalse(w.dock_jobs.visible)
        self.assertFalse(w._toolbar.visible)
        self.assertFalse(w._menu.visible)
        w._leave_basic()
        self.assertFalse(w._basic_active)
        self.assertIs(w.dock_jobs, original_dock)
        self.assertIs(w.pages.current, w.pages.advanced)
        self.assertEqual(w.restored_state, ('ADVANCED', 4))
        self.assertTrue(w._toolbar.visible)
        self.assertEqual(w.config.values['qt/v0111_interface_mode'], 'advanced')

    def test_close_basic_saves_advanced_layout_not_hidden_docks(self):
        w = self.window()
        w._enter_basic()
        class Event:
            def isAccepted(self): return True
        w.closeEvent(Event())
        self.assertEqual(w.config.values['qt/window_state'], 'ADVANCED')

    def test_cancelled_close_preserves_basic_layout_and_state(self):
        w = self.window()
        w._enter_basic()
        class Event:
            def isAccepted(self): return False
        w.closeEvent(Event())
        self.assertTrue(w._basic_active)
        self.assertNotIn('qt/window_state', w.config.values)
