"""v0.2.2-a1.9 regression: Run -> Work must shrink on the same screen.

No installed Qt, filesystem writes to Work or DWM job execution required.
Fake widget/layout classes exercise the real callback and its visible-item
measurement even when Qt's scrollable body and main minimum hints are stale.
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from app.basic_window_fit_v022_a1_8 import visible_basic_layout_height
import test_v022_a1_6_source_first as fixture


class Size:
    def __init__(self, height):
        self._h = height
    def height(self):
        return self._h


class Margin:
    def __init__(self, top=8, right=8, bottom=8, left=8):
        self._t, self._r, self._b, self._l = top, right, bottom, left
    def top(self): return self._t
    def right(self): return self._r
    def bottom(self): return self._b
    def left(self): return self._l


class Item:
    def __init__(self, height, *, widget=None, spacer=False, height_for_width=None):
        self._height, self._widget, self._spacer = height, widget, spacer
        self._height_for_width = height_for_width
    def widget(self): return self._widget
    def spacerItem(self): return self if self._spacer else None
    def isEmpty(self): return False
    def sizeHint(self): return Size(self._height)
    def hasHeightForWidth(self): return self._height_for_width is not None
    def heightForWidth(self, width): return self._height_for_width


class Visible:
    def __init__(self, *, hidden=False): self.hidden = hidden
    def isHidden(self): return self.hidden


class Layout:
    def __init__(self, items, *, margins=None, spacing=18):
        self.items = items
        self.margins = margins or Margin()
        self._spacing = spacing
    def invalidate(self): pass
    def activate(self): pass
    def contentsMargins(self): return self.margins
    def count(self): return len(self.items)
    def itemAt(self, index): return self.items[index]
    def spacing(self): return self._spacing


class VisibleHeightTests(unittest.TestCase):
    def test_hidden_run_and_stretched_viewport_do_not_inflate_work_hint(self):
        run, work, selector = Visible(hidden=True), Visible(), Visible(hidden=True)
        layout = Layout([
            Item(70), Item(120, widget=selector), Item(40),
            Item(180, widget=work), Item(720, widget=run),
            Item(900, spacer=True),  # QVBoxLayout final expanding stretch
        ])
        # Only three items contribute: header, navigation, active Work group.
        self.assertEqual(visible_basic_layout_height(layout, 980),
                         70 + 40 + 180 + 16 + 2 * 18)
        run.hidden, work.hidden, selector.hidden = False, True, False
        self.assertEqual(visible_basic_layout_height(layout, 980),
                         70 + 120 + 40 + 720 + 16 + 3 * 18)
        run.hidden, work.hidden, selector.hidden = True, False, True
        self.assertEqual(visible_basic_layout_height(layout, 980),
                         70 + 40 + 180 + 16 + 2 * 18)

    def test_wrapping_uses_height_for_width_even_in_compact_step(self):
        layout = Layout([Item(20, height_for_width=64)], spacing=0)
        self.assertEqual(visible_basic_layout_height(layout, 350), 80)


class RealCallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui = fixture.load_gui_class()

    def test_run_to_work_shrinks_after_large_run_even_when_old_qt_hints_remain(self):
        gui = self.gui
        w = object.__new__(gui)
        geom = {'x': 150, 'y': 70, 'w': 980, 'h': 575}
        initial_chrome = 150
        changes = []
        delayed = []
        work, run, selector = Visible(), Visible(hidden=True), Visible(hidden=True)
        content_layout = Layout([
            Item(70), Item(120, widget=selector), Item(40),
            Item(180, widget=work), Item(720, widget=run), Item(920, spacer=True),
        ])
        outer_layout = Layout([], margins=Margin(16, 16, 18, 16))

        class Rect:
            def __init__(self, x, y, width, height):
                self._x, self._y, self._w, self._h = x, y, width, height
            def y(self): return self._y
            def height(self): return self._h
            def center(self): return (self._x + self._w // 2,
                                      self._y + self._h // 2)

        class Body:
            def layout(self): return outer_layout
            # Both are deliberately incorrect/stale after showing Run.
            def sizeHint(self): return Size(1170)
            def minimumSizeHint(self): return Size(1110)

        class Scroll:
            def widget(self): return Body()
            def viewport(self):
                return types.SimpleNamespace(height=lambda: geom['h'] - initial_chrome,
                                             width=lambda: geom['w'])
            def verticalScrollBar(self):
                return types.SimpleNamespace(setValue=lambda value:
                                             changes.append(('scroll', value)))

        class Content:
            def layout(self): return content_layout
            def width(self): return geom['w']

        class SourceGroup:
            def parentWidget(self): return Content()

        class Page:
            def findChild(self, widget_type): return Scroll()

        class Screen:
            def availableGeometry(self): return Rect(0, 0, 1400, 1380)

        w._basic_page = Page()
        w._a2_step_groups = {'source': SourceGroup()}
        w._v022_auto_fit_allowed = lambda: True
        w._a14_window_positions = types.SimpleNamespace(_ready=True)
        w._v022_fit_pending = False
        w._v022_fit_started = False
        w._v022_fit_programmatic = False
        w._v022_last_fitted_step = None
        w.height = lambda: geom['h']
        w.width = lambda: geom['w']
        w.minimumHeight = lambda: 480
        # Deliberately stale as Qt may preserve the Run minimum across changes.
        w.minimumSizeHint = lambda: Size(1200)
        w.frameGeometry = lambda: Rect(geom['x'], geom['y'],
                                      geom['w'] + 12, geom['h'] + 30)
        w.screen = lambda: Screen()
        w.x = lambda: geom['x']
        w.y = lambda: geom['y']
        def resize(width, height):
            changes.append(('resize', width, height))
            geom['w'], geom['h'] = width, height
        def move(x, y):
            changes.append(('move', x, y))
            geom['x'], geom['y'] = x, y
        w.resize, w.move = resize, move

        widgets = types.ModuleType('PySide6.QtWidgets')
        widgets.QApplication = types.SimpleNamespace(
            screenAt=lambda center: Screen(), primaryScreen=lambda: Screen())
        widgets.QScrollArea = type('QScrollArea', (), {})
        core = types.ModuleType('PySide6.QtCore')
        core.QTimer = types.SimpleNamespace(singleShot=lambda delay, fn:
                                          delayed.append((delay, fn)))

        with patch.dict(sys.modules, {'PySide6.QtWidgets': widgets,
                                      'PySide6.QtCore': core}):
            w._a2_current_step = 'work'
            w._v022_apply_auto_fit()
            first_work = geom['h']
            self.assertLess(first_work, 650)
            # One saved work has now been presented; change to the tall Run tab.
            work.hidden, run.hidden, selector.hidden = True, False, False
            w._a2_current_step = 'run'
            w._v022_apply_auto_fit()
            self.assertGreater(geom['h'], 1000)
            # Switching back must shrink, despite enormous stale Qt sizeHints.
            work.hidden, run.hidden, selector.hidden = False, True, True
            w._a2_current_step = 'work'
            w._v022_apply_auto_fit()
            self.assertEqual(geom['h'], first_work)
            self.assertEqual(geom['x'], 150)
            self.assertGreaterEqual(geom['y'], 0)
            self.assertEqual(geom['w'], 980)
            self.assertEqual(w._v022_last_fitted_step, 'work')
            self.assertIn(('scroll', 0), changes)
            self.assertEqual(len([c for c in changes if c[0] == 'resize']), 3)

    def test_manual_resize_guard_still_respects_programmatic_and_pending_fit(self):
        gui = self.gui
        w = object.__new__(gui)
        w._v022_fit_ready = True
        w._v022_fit_started = True
        w._v022_auto_fit_enabled = True
        w._v022_fit_programmatic = False
        w._v022_fit_pending = False
        w._basic_active = True
        w.isVisible = lambda: True
        w.isMaximized = lambda: False
        w.isFullScreen = lambda: False
        w.isMinimized = lambda: False
        marked = []
        w._v022_mark_manual_size = lambda: marked.append(True)
        parent = gui.__mro__[1]
        with patch.object(parent, 'resizeEvent', lambda self, event: None,
                          create=True):
            # An internally requested resize must not disable auto-fit.
            w._v022_fit_programmatic = True
            w.resizeEvent(object())
            self.assertEqual(marked, [])
            w._v022_fit_programmatic = False
            w._v022_fit_pending = True
            w.resizeEvent(object())
            self.assertEqual(marked, [])
            # An unguarded user resize still disables auto-fit.
            w._v022_fit_pending = False
            w.resizeEvent(object())
            self.assertEqual(marked, [True])

    def test_second_layout_settle_is_scheduled_once_when_switching_steps(self):
        w = object.__new__(self.gui)
        w.api = fixture.API()
        w._active_id = None
        w._v022_draft = True
        w._v022_selector_signature = None
        w._v022_save_failed = False
        w._worker = None
        w._a2_current_step = 'source'
        w.v022_registration_status = fixture.Widget()
        w.v022_selector_group = fixture.Widget()
        w.v022_job_selector = fixture.Combo()
        w.v022_selector_caption = fixture.Widget()
        w.v022_current_job_label = fixture.Widget()
        w.v022_joblist_status = fixture.Widget()
        w.v022_new_job_button = fixture.Widget()
        w.v022_save_job_button = fixture.Widget()
        w.v022_save_list_button = fixture.Widget()
        w._v022_fit_ready = True
        w._basic_page = object()
        scheduled, timer = [], []
        w._v022_schedule_auto_fit = lambda: scheduled.append(w._a2_current_step)
        qtcore = types.ModuleType('PySide6.QtCore')
        qtcore.QTimer = types.SimpleNamespace(singleShot=lambda delay, callback:
                                               timer.append((delay, callback)))
        with patch.dict(sys.modules, {'PySide6.QtCore': qtcore}):
            w._a2_set_step('run')
        self.assertEqual(w._a2_current_step, 'run')
        self.assertEqual([delay for delay, _ in timer], [45])
        timer[0][1]()
        self.assertGreaterEqual(len(scheduled), 3)


if __name__ == '__main__':
    unittest.main()
