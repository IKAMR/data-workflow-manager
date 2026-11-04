"""a12: enforce legible Kjoereloep and Systemlogg Qt dock layout.

These tests execute the real production methods with small fake Qt surfaces.
The complete Windows GUI layout still needs a real PySide6 smoke test.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/'gui_qt'/'main_window.py').read_text(encoding='utf-8')
CLASS=next(n for n in ast.parse(SRC).body if isinstance(n,ast.ClassDef) and n.name=='DwmMainWindow')
METHODS={
    '_a12_activity_target_height', '_a12_activity_tab_changed',
    '_a12_ensure_activity_height', '_a12_size_initial_run_details',
    '_a12_restore_cramped_system_log', '_a12_system_visibility_changed',
    '_a12_arrange_system_log',
}
NODES=[n for n in CLASS.body if isinstance(n,ast.FunctionDef) and n.name in METHODS]

class FakeTimer:
    pending=[]
    @classmethod
    def singleShot(cls, timeout, callback):
        assert timeout==0
        cls.pending.append(callback)
    @classmethod
    def flush(cls):
        for _ in range(12):
            if not cls.pending: return
            cls.pending.pop(0)()
        raise AssertionError('Unexpected timer recursion')

Qt=SimpleNamespace(
    Orientation=SimpleNamespace(Vertical='vertical',Horizontal='horizontal'),
    DockWidgetArea=SimpleNamespace(BottomDockWidgetArea='bottom',RightDockWidgetArea='right'),
)
ns={'Qt':Qt,'QTimer':FakeTimer}
exec(compile(ast.fix_missing_locations(ast.Module(body=NODES,type_ignores=[])),
             '<a12-systemlog-layout>','exec'),ns)

class Dock:
    def __init__(self,*,area='bottom',height=195,width=610,visible=True,floating=False):
        self.area=area
        self._height=height
        self._width=width
        self.visible=visible
        self.floating=floating
    def isVisible(self): return self.visible
    def isFloating(self): return self.floating
    def height(self): return self._height
    def width(self): return self._width

class Tabs:
    def __init__(self,index=1): self.index=index
    def currentIndex(self): return self.index

class Splitter:
    def __init__(self,height=250): self._height=height;self.sizes=[]
    def height(self): return self._height
    def setSizes(self,sizes): self.sizes.append(sizes)

class Window:
    for_method_names=METHODS
    _a12_activity_target_height=ns['_a12_activity_target_height']
    _a12_activity_tab_changed=ns['_a12_activity_tab_changed']
    _a12_ensure_activity_height=ns['_a12_ensure_activity_height']
    _a12_size_initial_run_details=ns['_a12_size_initial_run_details']
    _a12_restore_cramped_system_log=ns['_a12_restore_cramped_system_log']
    _a12_system_visibility_changed=ns['_a12_system_visibility_changed']
    _a12_arrange_system_log=ns['_a12_arrange_system_log']
    def __init__(self):
        self._height=1170
        self._width=1280
        self.dock_jobs=Dock(area='left',width=350)
        self.dock_log=Dock()
        self.dock_system=Dock(width=190)
        self.activity_tabs=Tabs(1)
        self.run_history_splitter=Splitter()
        self._a12_run_splitter_initialized=False
        self._a12_system_split_active=False
        self.resizes=[]
        self.splits=[]
    def height(self): return self._height
    def width(self): return self._width
    def dockWidgetArea(self,dock): return dock.area
    def resizeDocks(self,docks,sizes,orientation):
        self.resizes.append((docks,sizes,orientation))
        if orientation=='vertical' and self.dock_log in docks:
            self.dock_log._height=sizes[docks.index(self.dock_log)]
    def splitDockWidget(self,a,b,direction): self.splits.append((a,b,direction))

class SystemLogAndActivityTests(unittest.TestCase):
    def setUp(self):
        FakeTimer.pending.clear()
        self.w=Window()

    def test_run_tab_grows_and_preserves_status_splitter(self):
        self.w._a12_ensure_activity_height()
        FakeTimer.flush()
        self.assertEqual(self.w.dock_log.height(),456)
        self.assertEqual(self.w.resizes[0][2],'vertical')
        self.assertTrue(self.w._a12_run_splitter_initialized)
        self.assertEqual(self.w.run_history_splitter.sizes,[[100,150]])

    def test_user_expanded_activity_is_not_shrunk(self):
        self.w.dock_log._height=570
        self.w._a12_ensure_activity_height()
        FakeTimer.flush()
        self.assertFalse(self.w.resizes)

    def test_log_tab_requires_less_height_than_run_tab(self):
        run=self.w._a12_activity_target_height()
        self.w.activity_tabs.index=0
        log=self.w._a12_activity_target_height()
        self.assertGreater(run,log)
        self.assertGreaterEqual(log,240)

    def test_switch_to_run_tab_schedules_growth(self):
        self.w.activity_tabs.index=1
        self.w._a12_activity_tab_changed(1)
        self.assertEqual(len(FakeTimer.pending),1)
        FakeTimer.flush()
        self.assertGreaterEqual(self.w.dock_log.height(),400)
        self.assertEqual(len(FakeTimer.pending),0)

    def test_open_system_log_splits_horizontally_and_grows_activity(self):
        self.w._a12_system_visibility_changed(True)
        FakeTimer.flush()
        self.assertEqual(self.w.splits,[(self.w.dock_log,self.w.dock_system,'horizontal')])
        horizontal=[a for a in self.w.resizes if a[2]=='horizontal']
        self.assertEqual(len(horizontal),1)
        self.assertGreater(horizontal[0][1][0],horizontal[0][1][1])
        self.assertGreaterEqual(horizontal[0][1][1],250)
        self.assertGreaterEqual(self.w.dock_log.height(),400)

    def test_reopening_visibility_does_not_repeat_native_split(self):
        self.w._a12_system_visibility_changed(True);FakeTimer.flush()
        self.w._a12_system_visibility_changed(True);FakeTimer.flush()
        self.assertEqual(len(self.w.splits),1)
        self.w._a12_system_visibility_changed(False)
        self.assertFalse(self.w._a12_system_split_active)
        self.w._a12_system_visibility_changed(True);FakeTimer.flush()
        self.assertEqual(len(self.w.splits),2)

    def test_other_dock_positions_or_floating_preserved(self):
        for area, floating in (('right',False),('bottom',True)):
            with self.subTest(area=area, floating=floating):
                self.w.dock_system.area=area
                self.w.dock_system.floating=floating
                self.w._a12_arrange_system_log()
                self.assertFalse(self.w.splits)
                self.assertFalse(self.w.resizes)

    def test_restore_repairs_only_narrow_system_on_wide_screen(self):
        self.w._a12_restore_cramped_system_log();FakeTimer.flush()
        self.assertEqual(len(self.w.splits),1)
        self.w.splits.clear();self.w.resizes.clear()
        self.w.dock_system._width=350
        self.w._a12_restore_cramped_system_log();FakeTimer.flush()
        self.assertFalse(self.w.splits)
        self.assertFalse(self.w.resizes)

    def test_small_window_retains_central_minimum(self):
        self.w._height=650
        self.assertLessEqual(self.w._a12_activity_target_height(),290)

    def test_new_signal_connections_are_after_settings_restore(self):
        start=SRC.index('        self._restore_settings()')
        conn=SRC.index('self.dock_system.visibilityChanged.connect(',start)
        self.assertGreater(conn,start)
        self.assertIn('self.activity_tabs.currentChanged.connect(self._a12_activity_tab_changed)',SRC)
        self.assertIn('self.run_history_splitter = history_splitter',SRC)
        self.assertIn('self.splitDockWidget(self.dock_log, self.dock_system, Qt.Orientation.Horizontal)',SRC)
        self.assertNotIn('tabifyDockWidget(',SRC)

if __name__=='__main__': unittest.main()
