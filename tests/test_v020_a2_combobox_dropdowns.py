"""Regression tests for dropdown placement after Qt's delayed native move.

The geometry and event-filter behavior can be tested without PySide6 installed.
The remaining actual Windows/DPI behavior is covered by the GUI checklist.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import unittest

from gui_qt.combobox_popup_v020_a2 import dropdown_origin, install_dropdown_positioning

ROOT = Path(__file__).resolve().parents[1]


class PopupGeometryTests(unittest.TestCase):
    def test_below_when_space_is_available(self):
        self.assertEqual(
            dropdown_origin(100, 250, 420, 48, 420, 120, 0, 0, 1920, 1080),
            (100, 298),
        )

    def test_above_if_lower_edge_cannot_fit_popup(self):
        self.assertEqual(
            dropdown_origin(100, 970, 420, 40, 420, 150, 0, 0, 1920, 1080),
            (100, 820),
        )

    def test_scroll_position_does_not_add_an_offset(self):
        self.assertEqual(
            dropdown_origin(60, 242, 900, 50, 900, 117, 0, 0, 1920, 1080),
            (60, 292),
        )

    def test_negative_coordinates_on_secondary_monitor(self):
        self.assertEqual(
            dropdown_origin(-1840, 200, 540, 40, 540, 100, -1920, 0, 1920, 1040),
            (-1840, 240),
        )

    def test_right_edge_and_rtl_are_respected(self):
        self.assertEqual(
            dropdown_origin(1760, 300, 210, 36, 380, 90, 0, 0, 1920, 1080),
            (1540, 336),
        )
        self.assertEqual(
            dropdown_origin(400, 300, 300, 36, 180, 90, 0, 0, 1920, 1080,
                            right_to_left=True),
            (520, 336),
        )

    def test_oversized_popup_is_clamped_to_available_screen(self):
        self.assertEqual(
            dropdown_origin(30, 300, 300, 36, 1000, 1500, 0, 0, 800, 600),
            (0, 0),
        )


class _Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y

    def __eq__(self, other):
        return isinstance(other, _Point) and (self._x, self._y) == (other._x, other._y)


class _Widget:
    def __init__(self, *, parent=None, pos=(0, 0), width=400, height=40, visible=True,
                 window=False, flags=0):
        self._parent = parent
        self._pos = _Point(*pos)
        self._width = width
        self._height = height
        self._visible = visible
        self._window = window
        self._flags = flags
        self.moves = 0

    def isVisible(self):
        return self._visible

    def isWindow(self):
        return self._window

    def parentWidget(self):
        return self._parent

    def windowFlags(self):
        return self._flags

    def mapToGlobal(self, point):
        return _Point(self._pos.x() + point.x(), self._pos.y() + point.y())

    def width(self):
        return self._width

    def height(self):
        return self._height

    def pos(self):
        return self._pos

    def move(self, new_pos):
        self.moves += 1
        self._pos = new_pos
        if self.on_move is not None:
            self.on_move()

    on_move = None

    def layoutDirection(self):
        return 0

    def screen(self):
        return _Screen()


class _ComboBox(_Widget):
    pass


class _Rect:
    def x(self): return 0
    def y(self): return 0
    def width(self): return 1920
    def height(self): return 1080


class _Screen:
    def availableGeometry(self):
        return _Rect()


class _FakeApplication:
    def __init__(self):
        self.installations = 0
        self.filter = None
        self.style = 'QComboBox { color: #fff; }'

    def installEventFilter(self, controller):
        self.installations += 1
        self.filter = controller

    def styleSheet(self):
        return self.style


class _Event:
    def __init__(self, event_type):
        self._type = event_type

    def type(self):
        return self._type


class FakeQtAnchorTests(unittest.TestCase):
    def setUp(self):
        self.timers = []
        QtCore = ModuleType('PySide6.QtCore')
        QtWidgets = ModuleType('PySide6.QtWidgets')
        QtGui = ModuleType('PySide6.QtGui')

        class QObject:
            def __init__(self, parent=None):
                self.parent = parent

        QtCore.QObject = QObject
        QtCore.QPoint = _Point
        QtCore.QEvent = SimpleNamespace(Type=SimpleNamespace(Show=17, Move=13, Resize=14))
        QtCore.QTimer = SimpleNamespace(singleShot=lambda ms, fn: self.timers.append((ms, fn)))
        QtCore.Qt = SimpleNamespace(WindowType=SimpleNamespace(Popup=1),
                                    LayoutDirection=SimpleNamespace(RightToLeft=1))
        QtWidgets.QComboBox = _ComboBox
        QtWidgets.QWidget = _Widget
        QtGui.QGuiApplication = SimpleNamespace(screenAt=lambda point: _Screen())
        self.modules = patch.dict(sys.modules, {
            'PySide6': ModuleType('PySide6'),
            'PySide6.QtCore': QtCore,
            'PySide6.QtWidgets': QtWidgets,
            'PySide6.QtGui': QtGui,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.app = _FakeApplication()
        install_dropdown_positioning(self.app)
        self.combo = _ComboBox(pos=(150, 250), width=350, height=40)
        self.popup = _Widget(parent=self.combo, pos=(150, 290), width=350,
                             height=105, window=True, flags=1)
        self.show = _Event(QtCore.QEvent.Type.Show)
        self.move = _Event(QtCore.QEvent.Type.Move)
        self.resize = _Event(QtCore.QEvent.Type.Resize)
        self.filter = self.app.filter

    def test_installs_once_for_existing_and_future_dialogs(self):
        install_dropdown_positioning(self.app)
        self.assertEqual(self.app.installations, 1)
        self.assertIs(self.app.filter, self.app._dwm_popup_anchor)

    def test_catches_native_move_after_initial_correct_show(self):
        self.filter.eventFilter(self.popup, self.show)
        self.popup._pos = _Point(150, 430)  # Qt's second, incorrect move
        self.filter.eventFilter(self.popup, self.move)
        self.assertEqual(self.popup.pos(), _Point(150, 290))
        for _delay, callback in self.timers:
            callback()
        self.assertEqual(self.popup.pos(), _Point(150, 290))

    def test_catches_resize_and_does_not_loop_on_its_own_move(self):
        self.popup._pos = _Point(150, 600)
        self.popup.on_move = lambda: self.filter.eventFilter(self.popup, self.move)
        self.filter.eventFilter(self.popup, self.resize)
        self.assertEqual(self.popup.moves, 1)
        self.assertEqual(self.popup.pos(), _Point(150, 290))

    def test_does_not_move_unrelated_popup_or_closed_dropdown(self):
        other_popup = _Widget(parent=_Widget(), pos=(400, 600), window=True, flags=1)
        self.filter.eventFilter(other_popup, self.move)
        self.assertEqual(other_popup.moves, 0)
        self.popup._visible = False
        self.popup._pos = _Point(150, 600)
        self.filter.eventFilter(self.popup, self.move)
        self.assertEqual(self.popup.moves, 0)

    def test_keeps_user_theme_and_does_not_replace_application_methods(self):
        self.assertEqual(self.app.style, 'QComboBox { color: #fff; }')
        self.assertFalse(hasattr(self.app, 'setStyleSheet'))


class RuntimeIntegrationTests(unittest.TestCase):
    def test_entrypoint_installs_app_filter_before_main_window_show(self):
        entry = (ROOT / 'gui_qt' / '__main__.py').read_text(encoding='utf-8')
        self.assertIn('from gui_qt.combobox_popup_v020_a2 import install_dropdown_positioning', entry)
        self.assertLess(entry.index('install_dropdown_positioning(application, window)'),
                        entry.index('window.show()'))

    def test_no_old_stylesheet_only_workaround(self):
        implementation = (ROOT / 'gui_qt' / 'combobox_popup_v020_a2.py').read_text(encoding='utf-8')
        self.assertNotIn('combobox-popup: 0', implementation)
        self.assertIn('QEvent.Type.Move', implementation)
        self.assertIn('obj.parentWidget()', implementation)
        self.assertIn('popup.move(target)', implementation)


if __name__ == '__main__':
    unittest.main()
