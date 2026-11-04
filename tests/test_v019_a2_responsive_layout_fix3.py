"""Headless regression: a2 result center must be usable on laptop and ultrawide.

Uses the actual Qt-adapter method AST without requiring a PySide6 installation.
All original action instances and signal connections are retained.
"""
from __future__ import annotations

import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / 'gui_qt' / 'result_center_v019_a1.py'
DEPOT = ROOT / 'gui_qt' / 'depot_review_v019_a2.py'


def _method(path, cls, name):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    klass = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == cls)
    method = next(x for x in klass.body if isinstance(x, ast.FunctionDef) and x.name == name)
    value = copy.deepcopy(method)
    value.decorator_list = []
    return value


class Area:
    def __init__(self, x, y, width, height):
        self._x, self._y, self._width, self._height = x, y, width, height

    def x(self): return self._x
    def y(self): return self._y
    def width(self): return self._width
    def height(self): return self._height


class Layout:
    def __init__(self, items=()):
        self.items = list(items)
        self.widgets = []
        self.layouts = []
        self.stretch = 0
        self.spacing = 0

    def count(self): return len(self.items)
    def takeAt(self, index): return self.items.pop(index)
    def itemAt(self, index): return self.items[index]
    def addLayout(self, item):
        self.layouts.append(item)
        self.items.append(SimpleNamespace(layout=lambda: item))
    def addItem(self, item): self.items.append(item)
    def insertWidget(self, index, widget): self.widgets.insert(index, widget)
    def setSpacing(self, n): self.spacing = n
    def addWidget(self, widget): self.widgets.append(widget)
    def addStretch(self, n): self.stretch += n


class Button:
    def __init__(self, name):
        self.name = name
        self.policy = None

    def setSizePolicy(self, horizontal, vertical):
        self.policy = (horizontal, vertical)


class Signal:
    def __init__(self): self.callbacks = []
    def connect(self, callback): self.callbacks.append(callback)


class ToolButton:
    ToolButtonPopupMode = SimpleNamespace(InstantPopup=1)
    def __init__(self, parent): self.parent = parent
    def setText(self, value): self.text = value
    def setPopupMode(self, value): self.mode = value
    def setMenu(self, menu): self.menu = menu


class Menu:
    def __init__(self, parent):
        self.aboutToShow = Signal()
        self.actions = []
    def clear(self): self.actions.clear()
    def addAction(self, label):
        action = SimpleNamespace(label=label, triggered=Signal(),
                                 setCheckable=lambda value: None,
                                 setChecked=lambda value: None)
        self.actions.append(action)
        return action


def _run_geometry(area):
    src = RESULT.read_text(encoding='utf-8')
    module = ast.parse(src)
    fn = next(x for x in module.body if isinstance(x, ast.FunctionDef) and
              x.name == '_normal_window_geometry')
    compiled = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    ns = {}
    exec(compile(compiled, str(RESULT), 'exec'), ns)
    return ns['_normal_window_geometry'](area)


class ResponsiveLayoutTests(unittest.TestCase):
    def test_ultrawide_opens_as_normal_readable_window(self):
        x, y, w, h = _run_geometry(Area(0, 0, 5120, 1440))
        self.assertEqual((w, h), (1380, 860))
        self.assertEqual((x, y), (1870, 290))
        self.assertNotEqual(w, 5120)

    def test_laptop_respects_available_work_area(self):
        x, y, w, h = _run_geometry(Area(0, 0, 1366, 768))
        self.assertEqual((w, h), (1286, 698))
        self.assertEqual((x, y), (40, 35))

    def test_secondary_monitor_coordinates_are_not_ignored(self):
        x, y, w, h = _run_geometry(Area(1920, -200, 1920, 1080))
        self.assertEqual((w, h), (1380, 860))
        self.assertEqual((x, y), (2190, -90))

    def test_small_screen_window_does_not_exceed_screen(self):
        x, y, w, h = _run_geometry(Area(0, 0, 800, 600))
        self.assertEqual((w, h), (760, 540))
        self.assertEqual((x, y), (20, 30))

    def test_existing_action_objects_keep_order_and_natural_width(self):
        method = _method(RESULT, 'ResultCenterWindow', '_configure_responsive_window')
        namespace = {
            'QHBoxLayout': Layout, 'QToolButton': ToolButton, 'QMenu': Menu,
            'QSizePolicy': SimpleNamespace(Policy=SimpleNamespace(Fixed=9)),
            '_normal_window_geometry': lambda rect: (100, 100, 1280, 800),
            'QApplication': SimpleNamespace(primaryScreen=lambda: None),
        }
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                     str(RESULT), 'exec'), namespace)
        buttons = [Button('action ' + str(i)) for i in range(7)]
        old = Layout([SimpleNamespace(widget=lambda x=button: x) for button in buttons] +
                     [SimpleNamespace(widget=lambda: None)])
        heading = Layout()
        outer = Layout([SimpleNamespace(layout=lambda: heading),
                        SimpleNamespace(layout=lambda: None),
                        SimpleNamespace(layout=lambda: old)])
        tabbar = SimpleNamespace(setUsesScrollButtons=lambda v: setattr(tabbar, 'scroll', v))
        panel = SimpleNamespace(tabBar=lambda: tabbar)

        class Screen:
            def availableGeometry(self): return Area(0, 0, 1920, 1080)

        class Window:
            tabs = panel
            _populate_tab_menu = lambda self: None
            def layout(self): return outer
            def setMinimumSize(self, w, h): self.minimum = (w, h)
            def parentWidget(self): return None
            def screen(self): return Screen()
            def setGeometry(self, x, y, w, h): self.geometry = (x, y, w, h)
            def resize(self, w, h): self.fallback = (w, h)

        window = Window()
        namespace['_configure_responsive_window'](window)
        self.assertEqual(window.minimum, (760, 540))
        self.assertEqual(window.geometry, (100, 100, 1280, 800))
        self.assertEqual(len(outer.layouts), 2)
        self.assertEqual(outer.layouts[0].widgets, buttons[:4])
        self.assertEqual(outer.layouts[1].widgets, buttons[4:])
        self.assertTrue(all(row.stretch == 1 for row in outer.layouts))
        self.assertTrue(all(button.policy == (9, 9) for button in buttons))
        self.assertEqual([row.spacing for row in outer.layouts], [6, 6])
        self.assertEqual(len(heading.widgets), 1)
        self.assertEqual(heading.widgets[0].text, 'Faner...')
        self.assertTrue(tabbar.scroll)

    def test_tab_navigation_still_reaches_last_tab(self):
        method = _method(RESULT, 'ResultCenterWindow', '_populate_tab_menu')
        ns = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                     str(RESULT), 'exec'), ns)
        menu = Menu(None)
        tab = SimpleNamespace(currentIndex=lambda: 0, count=lambda: 13,
                              tabText=lambda i: 'Tab ' + str(i),
                              setCurrentIndex=lambda i: setattr(tab, 'selected', i))
        ns['_populate_tab_menu'](SimpleNamespace(_tab_menu=menu, tabs=tab))
        self.assertEqual(len(menu.actions), 13)
        menu.actions[-1].triggered.callbacks[0](False)
        self.assertEqual(tab.selected, 12)

    def test_depot_buttons_are_compact_and_panel_still_resizable(self):
        src = DEPOT.read_text(encoding='utf-8')
        tree = ast.parse(src)
        panel = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                     and x.name == 'DepotReviewPanel')
        init = next(x for x in panel.body if isinstance(x, ast.FunctionDef)
                    and x.name == '__init__')
        body = ast.get_source_segment(src, init)
        self.assertIn('for items in ((self.review_button, self.period_button, self.detail_button)', body)
        self.assertIn('button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)', body)
        self.assertIn('row.addStretch(1)', body)
        self.assertIn('layout.addLayout(row)', body)
        self.assertNotIn('QGridLayout', body)
        self.assertIn('splitter.setChildrenCollapsible(False)', body)
        self.assertIn('self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)', body)
        for signal in ('self.review_button.clicked.connect(self._review_selected)',
                       'self.period_button.clicked.connect(self._period_selected)',
                       'self.detail_button.clicked.connect(self._open_large_details)'):
            self.assertIn(signal, body)

    def test_no_forced_maximize_or_changed_depot_services(self):
        result = RESULT.read_text(encoding='utf-8')
        depot = DEPOT.read_text(encoding='utf-8')
        self.assertNotIn('WindowMaximized', result)
        self.assertNotIn('showMaximized', result)
        self.assertNotIn('setWindowState(', result)
        self.assertIn('record_depot_review(self.row, status=code, reason=note, user=self.user)', depot)
        self.assertIn('ReviewEvidenceDialog(row, self).exec()', depot)
        self.assertNotIn('customtkinter', result)
        self.assertNotIn('customtkinter', depot)


if __name__ == '__main__':
    unittest.main()
