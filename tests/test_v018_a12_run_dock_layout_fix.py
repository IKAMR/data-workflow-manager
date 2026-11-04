"""a12: One compact tabbed activity dock, not stacked native Qt docks."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / 'gui_qt' / 'main_window.py').read_text(encoding='utf-8')
CLS = next(n for n in ast.parse(SRC).body if isinstance(n, ast.ClassDef) and n.name == 'DwmMainWindow')
NAMES = (
    '_a12_detach_active_tab', '_a12_reconcile_activity_tabs',
    '_a12_activate_activity_tab', '_a12_show_run_tab',
    '_a12_show_log_tab', '_a12_balance_workspace',
    '_a12_activity_target_height',
)
NODES = [n for n in CLS.body if isinstance(n, ast.FunctionDef) and n.name in NAMES]
Qt = SimpleNamespace(
    Orientation=SimpleNamespace(Vertical='vertical',Horizontal='horizontal'),
    DockWidgetArea=SimpleNamespace(LeftDockWidgetArea='left', BottomDockWidgetArea='bottom'),
)
ns = {'Qt': Qt}
exec(compile(ast.fix_missing_locations(ast.Module(body=NODES, type_ignores=[])), '<tabs>', 'exec'), ns)


class Tabs:
    def __init__(self): self.visible = [True,True]; self.current = 1
    def setTabVisible(self, index, visible):
        self.visible[index] = bool(visible)
        if not self.visible[self.current]:
            self.current = next((i for i, v in enumerate(self.visible) if v), self.current)
    def isTabVisible(self, index): return self.visible[index]
    def setCurrentIndex(self, index): self.current=index
    def currentIndex(self): return self.current


class Dock:
    def __init__(self, visible=True, area='left'):
        self.visible=visible; self.area=area; self.floating=False
        self.show_count=0
    def show(self): self.visible=True; self.show_count += 1
    def hide(self): self.visible=False
    def isVisible(self): return self.visible
    def isFloating(self): return self.floating
    def raise_(self): pass


class Viewer:
    def __init__(self): self.shown=0
    def show(self): self.shown+=1
    def raise_(self): pass


class Window:
    _a12_detach_active_tab = ns['_a12_detach_active_tab']
    _a12_reconcile_activity_tabs = ns['_a12_reconcile_activity_tabs']
    _a12_activate_activity_tab = ns['_a12_activate_activity_tab']
    _a12_show_run_tab = ns['_a12_show_run_tab']
    _a12_show_log_tab = ns['_a12_show_log_tab']
    _a12_balance_workspace = ns['_a12_balance_workspace']
    _a12_activity_target_height = ns['_a12_activity_target_height']

    def __init__(self):
        self.activity_tabs=Tabs()
        self.dock_log=Dock(area="bottom")
        self.dock_run=Dock(False)
        self.dock_jobs=Dock()
        self.dock_workflow=Dock()
        self._detached_log_window=None
        self._detached_run_window=None
        self.run_detaches=0
        self.log_detaches=0
        self.resizes=[]
    def _a9_float_run(self): self.run_detaches+=1
    def _a8_float_job_log(self): self.log_detaches+=1
    def height(self): return 1000
    def dockWidgetArea(self, dock): return dock.area
    def resizeDocks(self, docks, sizes, axis): self.resizes.append((docks,sizes,axis))
    def _a12_balance_left_docks(self): pass


class UnifiedActivityLayoutTests(unittest.TestCase):
    def setUp(self): self.w=Window()

    def test_one_real_dock_and_two_normal_tabs(self):
        self.assertIn('self.activity_tabs.addTab(logger, "Kjørelogg")',SRC)
        self.assertIn('self.activity_tabs.addTab(flow_progress, "Kjøreløp")',SRC)
        self.assertIn('self._dock("log", "Aktivitet", self.activity_tabs,',SRC)
        self.assertIn('self.dock_run.hide()  # Never allow the old second bottom dock.',SRC)
        self.assertIn('if name == "run":\n                continue',SRC)
        self.assertNotIn('tabifyDockWidget(',SRC)
        self.assertNotIn('splitDockWidget(self.dock_log, self.dock_run',SRC)
        self.assertNotIn('QMainWindow.DockOption.AllowTabbedDocks',SRC)

    def test_run_tab_selects_existing_panel_not_a_second_dock(self):
        self.w.activity_tabs.setCurrentIndex(0)
        self.w.dock_log.hide()
        self.w._a12_show_run_tab()
        self.assertEqual(self.w.activity_tabs.currentIndex(),1)
        self.assertTrue(self.w.dock_log.visible)
        self.assertFalse(self.w.dock_run.visible)

    def test_log_tab_activates_without_docking_changes(self):
        self.w._a12_show_log_tab()
        self.assertEqual(self.w.activity_tabs.currentIndex(),0)
        self.assertFalse(self.w.dock_run.visible)

    def test_detach_hides_only_selected_tab(self):
        self.w._detached_run_window=Viewer()
        self.w._a12_reconcile_activity_tabs()
        self.assertEqual(self.w.activity_tabs.visible,[True,False])
        self.assertTrue(self.w.dock_log.visible)
        self.w._a12_show_run_tab()
        self.assertEqual(self.w._detached_run_window.shown,1)
        self.assertEqual(self.w.activity_tabs.visible,[True,False])

    def test_both_detached_hides_common_panel_and_redock_recovers(self):
        self.w._detached_run_window=Viewer()
        self.w._detached_log_window=Viewer()
        self.w._a12_reconcile_activity_tabs()
        self.assertEqual(self.w.activity_tabs.visible,[False,False])
        self.assertFalse(self.w.dock_log.visible)
        self.w._detached_run_window=None
        self.w._a12_show_run_tab()
        self.assertEqual(self.w.activity_tabs.visible,[False,True])
        self.assertTrue(self.w.dock_log.visible)

    def test_header_detaches_current_tab(self):
        self.w.activity_tabs.setCurrentIndex(1)
        self.w._a12_detach_active_tab()
        self.assertEqual(self.w.run_detaches,1)
        self.w.activity_tabs.setCurrentIndex(0)
        self.w._a12_detach_active_tab()
        self.assertEqual(self.w.log_detaches,1)

    def test_default_sizes_leave_central_area_and_widen_left(self):
        self.w._a12_balance_workspace()
        self.assertEqual(len(self.w.resizes),2)
        self.assertEqual(self.w.resizes[0][2],'horizontal')
        self.assertEqual(self.w.resizes[1][0],[self.w.dock_log])
        self.assertEqual(self.w.resizes[1][2],'vertical')
        self.assertGreaterEqual(self.w.resizes[1][1][0],355)
        self.assertLessEqual(self.w.resizes[1][1][0],460)

    def test_one_time_restore_migrates_old_stacked_layout(self):
        self.assertIn('qt/a12_unified_activity_initialized',SRC)
        self.assertIn('if state and migrated:',SRC)
        self.assertIn('self.config.setValue("qt/a12_unified_activity_initialized", True)',SRC)
        self.assertIn('self.dock_run.hide()  # Do not persist obsolete bottom split.',SRC)


if __name__ == '__main__': unittest.main()
