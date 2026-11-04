"""a12: Vis must reflect the ACTIVE activity tab, not only dock visibility.

Headless AST execution avoids depending on PySide6 in developer CI. The real
Windows GUI still needs the user's end-to-end test.bat and a visual smoke test.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
CLASS = next(node for node in ast.parse(SRC).body if isinstance(node, ast.ClassDef) and node.name == "DwmMainWindow")
NAMES = {"_a12_sync_activity_menu", "_a12_activate_activity_tab", "_a12_show_log_tab", "_a12_show_run_tab"}
NODES = [node for node in CLASS.body if isinstance(node, ast.FunctionDef) and node.name in NAMES]
ns = {}
exec(compile(ast.fix_missing_locations(ast.Module(body=NODES, type_ignores=[])), "<a12-view-menu>", "exec"), ns)


class Action:
    def __init__(self):
        self.checked = False
    def setChecked(self, checked):
        self.checked = bool(checked)


class Dock:
    def __init__(self, visible=True):
        self.visible = visible
        self.on_visibility = None
    def isVisible(self):
        return self.visible
    def show(self):
        was_visible = self.visible
        self.visible = True
        if not was_visible and self.on_visibility:
            self.on_visibility(True)
    def hide(self):
        was_visible = self.visible
        self.visible = False
        if was_visible and self.on_visibility:
            self.on_visibility(False)
    def raise_(self):
        pass


class Tabs:
    def __init__(self):
        self.index = 1
        self.visible = [True, True]
        self.on_changed = None
    def currentIndex(self):
        return self.index
    def setCurrentIndex(self, index):
        if self.index != index:
            self.index = index
            if self.on_changed:
                self.on_changed(index)
    def isTabVisible(self, index):
        return self.visible[index]
    def setTabVisible(self, index, visible):
        self.visible[index] = visible


class Detached:
    def __init__(self, visible=True):
        self.visible = visible
        self.shown = 0
    def isVisible(self):
        return self.visible
    def show(self):
        self.visible = True
        self.shown += 1
    def raise_(self):
        pass


class Window:
    _a12_sync_activity_menu = ns["_a12_sync_activity_menu"]
    _a12_activate_activity_tab = ns["_a12_activate_activity_tab"]
    _a12_show_log_tab = ns["_a12_show_log_tab"]
    _a12_show_run_tab = ns["_a12_show_run_tab"]
    def __init__(self):
        self.activity_tabs = Tabs()
        self.dock_log = Dock()
        self._detached_log_window = None
        self._detached_run_window = None
        self.show_job_log_action = Action()
        self.show_run_tab_action = Action()
        self.activity_tabs.on_changed = self._a12_sync_activity_menu
        self.dock_log.on_visibility = self._a12_sync_activity_menu
        self._a12_sync_activity_menu()


class ViewMenuConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.w = Window()

    def test_run_is_checked_at_start_but_log_is_not(self):
        self.assertTrue(self.w.show_run_tab_action.checked)
        self.assertFalse(self.w.show_job_log_action.checked)

    def test_show_log_switches_checked_item(self):
        self.w._a12_show_log_tab()
        self.assertTrue(self.w.show_job_log_action.checked)
        self.assertFalse(self.w.show_run_tab_action.checked)

    def test_selecting_same_active_tab_keeps_it_checked(self):
        self.w._a12_show_log_tab()
        self.w.show_job_log_action.setChecked(False)  # Qt transient click state
        self.w._a12_show_log_tab()
        self.assertTrue(self.w.show_job_log_action.checked)
        self.assertFalse(self.w.show_run_tab_action.checked)

    def test_switching_back_to_run_updates_checks(self):
        self.w._a12_show_log_tab()
        self.w._a12_show_run_tab()
        self.assertFalse(self.w.show_job_log_action.checked)
        self.assertTrue(self.w.show_run_tab_action.checked)

    def test_hidden_activity_checks_neither_tab(self):
        self.w.dock_log.hide()
        self.assertFalse(self.w.show_job_log_action.checked)
        self.assertFalse(self.w.show_run_tab_action.checked)
        self.w._a12_show_log_tab()
        self.assertTrue(self.w.show_job_log_action.checked)

    def test_systemlog_visibility_does_not_change_selected_activity_tab(self):
        self.w._a12_show_run_tab()
        system = Dock(visible=False)
        system.show()
        self.w._a12_sync_activity_menu()
        self.assertTrue(self.w.show_run_tab_action.checked)
        self.assertFalse(self.w.show_job_log_action.checked)

    def test_reset_to_default_run_tab_is_checked(self):
        self.w._a12_show_log_tab()
        # Same GUI state change made by Tilbakestill vinduer/Laptop preset.
        self.w.activity_tabs.setCurrentIndex(1)
        self.assertTrue(self.w.show_run_tab_action.checked)
        self.assertFalse(self.w.show_job_log_action.checked)

    def test_detached_log_is_not_a_checked_activity_tab(self):
        self.w._detached_log_window = Detached()
        self.w.activity_tabs.setTabVisible(0, False)
        self.w._a12_sync_activity_menu()
        self.assertFalse(self.w.show_job_log_action.checked)
        self.assertTrue(self.w.show_run_tab_action.checked)
        # A separate window's visibility does not change the active tab.
        self.w._detached_log_window.visible = False
        self.w._a12_sync_activity_menu()
        self.assertFalse(self.w.show_job_log_action.checked)
        self.assertTrue(self.w.show_run_tab_action.checked)

    def test_detached_run_without_activity_panel_has_no_checked_tab(self):
        self.w.dock_log.hide()
        self.w._detached_run_window = Detached()
        self.w._a12_sync_activity_menu()
        self.assertFalse(self.w.show_run_tab_action.checked)
        self.assertFalse(self.w.show_job_log_action.checked)

    def test_menu_actions_are_checkable_and_keep_native_dock_action(self):
        self.assertIn('self.show_job_log_action.setCheckable(True)', SRC)
        self.assertIn('self.show_run_tab_action.setCheckable(True)', SRC)
        self.assertIn('view.aboutToShow.connect(self._a12_sync_activity_menu)', SRC)
        self.assertIn('self.activity_tabs.currentChanged.connect(self._a12_sync_activity_menu)', SRC)
        self.assertIn('self.dock_log.visibilityChanged.connect(self._a12_sync_activity_menu)', SRC)
        self.assertIn('toggle = getattr(self, "dock_" + name).toggleViewAction()', SRC)

    def test_visibility_and_tab_selection_have_distinct_menu_actions(self):
        self.assertIn('activity_view_menu = view.addMenu("Aktivitetsfane")', SRC)
        self.assertIn('activity_view_menu.addAction(self.show_job_log_action)', SRC)
        self.assertIn('activity_view_menu.addAction(self.show_run_tab_action)', SRC)
        self.assertIn('self.show_job_log_action = self._action("Kjørelogg",', SRC)
        self.assertNotIn('self.show_job_log_action = self._action("Vis kjørelogg",', SRC)
        self.assertIn('toggle = getattr(self, "dock_" + name).toggleViewAction()', SRC)

    def test_toolbar_has_separate_noncheckable_go_to_log_action(self):
        self.assertIn('self.goto_job_log_action = self._action(', SRC)
        self.assertIn('"Gå til kjørelogg", self._a8_show_job_log,', SRC)
        self.assertIn('toolbar.addAction(self.goto_job_log_action)', SRC)
        self.assertNotIn('toolbar.addAction(self.show_job_log_action)', SRC)
        self.assertNotIn('self.goto_job_log_action.setCheckable(True)', SRC)

    def test_selecting_hidden_log_tab_shows_activity_panel(self):
        self.w.dock_log.hide()
        self.w._a12_show_log_tab()
        self.assertTrue(self.w.dock_log.isVisible())
        self.assertEqual(self.w.activity_tabs.currentIndex(), 0)
        self.assertTrue(self.w.show_job_log_action.checked)
        self.assertFalse(self.w.show_run_tab_action.checked)

    def test_no_native_tabbed_docks_or_second_run_dock(self):
        self.assertIn('self.dock_run.hide()  # Never allow the old second bottom dock.', SRC)
        self.assertNotIn('tabifyDockWidget(', SRC)

if __name__ == '__main__':
    unittest.main()
