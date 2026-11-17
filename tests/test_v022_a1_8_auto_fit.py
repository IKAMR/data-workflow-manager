"""v0.2.2-a1.8: step-aware Qt window height and manual override.

Pure geometry + fake-Qt checks; no monitor, Work, jobs or Qt installation needed.
The real Windows / multi-monitor GUI remains the operator acceptance test.
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from app.basic_window_fit_v022_a1_8 import fit_basic_height, should_auto_fit
import test_v022_a1_6_source_first as fixture


class GeometryTests(unittest.TestCase):
    def test_source_and_work_shrink_to_natural_content(self):
        source = fit_basic_height(content_height=520, viewport_height=900,
                                  window_height=1020, minimum_height=480,
                                  screen_top=0, screen_height=1200,
                                  frame_top=80, frame_extra=30)
        work = fit_basic_height(content_height=350, viewport_height=900,
                                window_height=1020, minimum_height=480,
                                screen_top=0, screen_height=1200,
                                frame_top=80, frame_extra=30)
        self.assertEqual(source.window_height, 660)
        self.assertEqual(work.window_height, 490)
        self.assertFalse(source.requires_scrolling)
        self.assertFalse(work.requires_scrolling)

    def test_run_expands_to_its_actual_content_height(self):
        result = fit_basic_height(content_height=940, viewport_height=420,
                                  window_height=565, minimum_height=480,
                                  screen_top=0, screen_height=1300,
                                  frame_top=80, frame_extra=30)
        self.assertEqual(result.window_height, 1105)
        self.assertEqual(result.frame_top, 80)
        self.assertFalse(result.requires_scrolling)

    def test_short_screen_clamps_run_and_requires_scrollbar(self):
        result = fit_basic_height(content_height=940, viewport_height=420,
                                  window_height=565, minimum_height=480,
                                  screen_top=0, screen_height=806,
                                  frame_top=40, frame_extra=30)
        self.assertEqual(result.window_height, 760)
        self.assertEqual(result.frame_top, 8)
        self.assertTrue(result.requires_scrolling)

    def test_never_exceeds_current_monitor_or_moves_x(self):
        result = fit_basic_height(content_height=540, viewport_height=460,
                                  window_height=570, minimum_height=480,
                                  screen_top=960, screen_height=900,
                                  frame_top=1500, frame_extra=32)
        self.assertEqual(result.window_height, 670)
        self.assertEqual(result.frame_top, 1150)
        self.assertFalse(result.requires_scrolling)

    def test_preserves_vertical_position_if_enough_room(self):
        result = fit_basic_height(content_height=300, viewport_height=450,
                                  window_height=520, minimum_height=480,
                                  screen_top=-100, screen_height=1000,
                                  frame_top=175, frame_extra=27)
        self.assertEqual(result.window_height, 480)
        self.assertEqual(result.frame_top, 175)

    def test_scroll_fallback_when_screen_shorter_than_minimum(self):
        result = fit_basic_height(content_height=970, viewport_height=300,
                                  window_height=500, minimum_height=480,
                                  screen_top=0, screen_height=410,
                                  frame_top=0, frame_extra=30)
        self.assertEqual(result.window_height, 480)  # Qt enforces this minimum
        self.assertTrue(result.requires_scrolling)

    def test_unusable_dimensions_are_guarded(self):
        result = fit_basic_height(content_height=-1, viewport_height=0,
                                  window_height=0, minimum_height=10,
                                  screen_top=0, screen_height=400,
                                  frame_top=50, frame_extra=-1)
        self.assertGreaterEqual(result.window_height, 10)

    def test_maximized_fullscreen_minimized_and_manual_never_auto_resize(self):
        defaults = dict(ready=True, basic=True, page_visible=True,
                        window_visible=True, maximized=False, fullscreen=False,
                        minimized=False, manual_override=False)
        self.assertTrue(should_auto_fit(**defaults))
        for key in ('ready', 'basic', 'page_visible', 'window_visible'):
            self.assertFalse(should_auto_fit(**(defaults | {key: False})), key)
        for key in ('maximized', 'fullscreen', 'minimized', 'manual_override'):
            self.assertFalse(should_auto_fit(**(defaults | {key: True})), key)


class GuiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui = fixture.load_gui_class()

    def test_stage_change_schedules_fit_without_affecting_job_ui(self):
        legacy = fixture.SourceFirstTests()
        legacy.window_class = self.gui
        w = legacy.window()
        w._v022_fit_ready = True
        scheduled = []
        w._v022_schedule_auto_fit = lambda: scheduled.append(w._a2_current_step)
        w._a2_set_step('run')
        self.assertEqual(w._a2_current_step, 'run')
        self.assertTrue(w.v022_selector_group.visible is False)  # no jobs
        self.assertGreaterEqual(len(scheduled), 2)

    def test_manual_resize_disables_until_opted_in(self):
        w = object.__new__(self.gui)
        values = []
        w.config = types.SimpleNamespace(setValue=lambda key, value:
                                         values.append((key, value)))
        w.v022_fit_window_button = fixture.Widget()
        w._v022_auto_fit_enabled = True
        w._v022_mark_manual_size()
        self.assertFalse(w._v022_auto_fit_enabled)
        self.assertTrue(w.v022_fit_window_button.visible)
        self.assertEqual(values, [('qt/v022_basic_auto_fit', False)])
        w._v022_schedule_auto_fit = lambda: values.append(('fit', None))
        w._v022_enable_auto_fit()
        self.assertTrue(w._v022_auto_fit_enabled)
        self.assertFalse(w.v022_fit_window_button.visible)
        self.assertEqual(values[-2:], [('qt/v022_basic_auto_fit', True), ('fit', None)])

    def test_queued_request_coalesces_step_updates(self):
        w = object.__new__(self.gui)
        w._v022_fit_ready = True
        w._v022_fit_pending = False
        w._v022_auto_fit_allowed = lambda: True
        scheduled = []
        qt = types.ModuleType('PySide6.QtCore')
        qt.QTimer = types.SimpleNamespace(singleShot=lambda delay, action:
                                          scheduled.append((delay, action)))
        with patch.dict(sys.modules, {'PySide6.QtCore': qt}):
            w._v022_schedule_auto_fit()
            w._v022_schedule_auto_fit()
        self.assertTrue(w._v022_fit_pending)
        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0][0], 0)

    def test_actual_fit_callback_uses_active_scroll_content_and_same_screen(self):
        # Exercise the real subclass method, not just the pure height helper.
        gui = self.gui
        w = object.__new__(gui)
        geometry = {'x': 80, 'y': 80, 'w': 980, 'h': 565}
        changes = []
        delayed = []

        class Rect:
            def __init__(self, x, y, width, height):
                self._x, self._y = x, y
                self._w, self._h = width, height
            def y(self): return self._y
            def height(self): return self._h
            def center(self): return (self._x + self._w // 2,
                                      self._y + self._h // 2)

        class Layout:
            def invalidate(self): pass
            def activate(self): pass
            def hasHeightForWidth(self): return False

        class Body:
            def layout(self): return Layout()
            def sizeHint(self): return types.SimpleNamespace(height=lambda: 940)
            def minimumSizeHint(self): return types.SimpleNamespace(height=lambda: 500)

        class Scrollbar:
            def setValue(self, value): changes.append(('scroll', value))

        class Scroll:
            def widget(self): return Body()
            def viewport(self):
                return types.SimpleNamespace(height=lambda: 420, width=lambda: 1000)
            def verticalScrollBar(self): return Scrollbar()

        class Page:
            def findChild(self, widget_type): return Scroll()

        class Screen:
            def availableGeometry(self): return Rect(0, 0, 1300, 1260)

        w._basic_page = Page()
        w._v022_auto_fit_allowed = lambda: True
        w._a14_window_positions = types.SimpleNamespace(_ready=True)
        w._v022_fit_pending = True
        w._v022_fit_started = False
        w._v022_fit_programmatic = False
        w._v022_last_fitted_step = None
        w._a2_current_step = 'run'
        w.height = lambda: geometry['h']
        w.width = lambda: geometry['w']
        w.minimumHeight = lambda: 480
        w.minimumSizeHint = lambda: types.SimpleNamespace(height=lambda: 480)
        w.frameGeometry = lambda: Rect(geometry['x'], geometry['y'],
                                      geometry['w'] + 16, geometry['h'] + 30)
        w.screen = lambda: Screen()
        w.x = lambda: geometry['x']
        w.y = lambda: geometry['y']

        def resize(width, height):
            changes.append(('resize', width, height))
            geometry['w'], geometry['h'] = width, height
        def move(x, y):
            changes.append(('move', x, y))
            geometry['x'], geometry['y'] = x, y
        w.resize = resize
        w.move = move

        widgets = types.ModuleType('PySide6.QtWidgets')
        widgets.QApplication = types.SimpleNamespace(
            screenAt=lambda center: Screen(), primaryScreen=lambda: Screen())
        widgets.QScrollArea = type('QScrollArea', (), {})
        core = types.ModuleType('PySide6.QtCore')
        core.QTimer = types.SimpleNamespace(singleShot=lambda delay, fn:
                                          delayed.append((delay, fn)))
        with patch.dict(sys.modules, {'PySide6.QtWidgets': widgets,
                                      'PySide6.QtCore': core}):
            w._v022_apply_auto_fit()
        self.assertIn(('resize', 980, 1105), changes)
        self.assertEqual(geometry['x'], 80)
        self.assertEqual(geometry['y'], 80)
        self.assertIn(('scroll', 0), changes)
        self.assertTrue(w._v022_fit_started)
        self.assertEqual(len(delayed), 1)
        self.assertEqual(delayed[0][0], 0)
        # Recomputing while a job is running must not forcibly scroll the
        # operator to the top on each progress update.
        changes.clear()
        with patch.dict(sys.modules, {'PySide6.QtWidgets': widgets,
                                      'PySide6.QtCore': core}):
            w._v022_apply_auto_fit()
        self.assertNotIn(('scroll', 0), changes)

    def test_resize_implementation_keeps_width_and_respects_fit_disable(self):
        src = (fixture.ROOT / 'gui_qt/basic_multijob_v022_a1_2.py').read_text(encoding='utf-8')
        self.assertIn('self.resize(self.width(), choice.window_height)', src)
        self.assertIn('self._v022_fit_programmatic', src)
        self.assertIn('scroll.verticalScrollBar().setValue(0)', src)
        self.assertIn('QApplication.screenAt(frame.center())', src)
        self.assertIn('v022_basic_fit_window', src)
        self.assertIn('and page.isVisible()', src)  # do not resize Startside


if __name__ == '__main__':
    unittest.main()
