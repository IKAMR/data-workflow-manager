"""a16.2: Periodevurdering and Depotvurdering are direct, synced buttons.

A small Qt double verifies navigation even on CI without a graphical display.
The production Qt widget remains the only implementation under test.
"""
from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import ast
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'result_navigation_v020_a6.py'


class _Signal:
    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *args):
        for slot in tuple(self._slots):
            slot(*args)


class _Widget:
    def __init__(self, parent=None):
        self.parent = parent
        self.visible = True
        self.object_name = ''

    def setObjectName(self, value):
        self.object_name = value

    def setVisible(self, visible):
        self.visible = bool(visible)


class _Layout:
    def __init__(self, *_args):
        self.widgets = []

    def setContentsMargins(self, *_args):
        pass

    def setSpacing(self, *_args):
        pass

    def addWidget(self, value):
        self.widgets.append(value)

    def addLayout(self, value):
        self.widgets.append(value)

    def addStretch(self, *_args):
        pass


class _TabBar(_Widget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged = _Signal()
        self._titles = []
        self._index = -1
        self._blocked = False

    def setExpanding(self, _value):
        pass

    def setUsesScrollButtons(self, _value):
        pass

    def setElideMode(self, _value):
        pass

    def addTab(self, value):
        self._titles.append(value)
        if self._index < 0:
            self._index = 0

    def blockSignals(self, value):
        self._blocked = bool(value)

    def setCurrentIndex(self, index):
        if self._index == index:
            return
        self._index = index
        if not self._blocked:
            self.currentChanged.emit(index)

    def currentIndex(self):
        return self._index


class _ComboBox(_Widget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentIndexChanged = _Signal()
        self._items = []
        self._index = -1
        self._blocked = False

    def setMinimumWidth(self, _value):
        pass

    def blockSignals(self, value):
        self._blocked = bool(value)

    def clear(self):
        self._items = []
        self._index = -1

    def addItem(self, label, data):
        self._items.append((label, data))

    def findData(self, data):
        return next((i for i, (_label, item) in enumerate(self._items)
                     if item == data), -1)

    def setCurrentIndex(self, index):
        if self._index == index:
            return
        self._index = index
        if not self._blocked:
            self.currentIndexChanged.emit(index)

    def currentData(self):
        return self._items[self._index][1] if 0 <= self._index < len(self._items) else None


class _Button(_Widget):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.label = label
        self.clicked = _Signal()
        self._checked = False
        self._group = None

    def setCheckable(self, _value):
        pass

    def setMinimumWidth(self, _value):
        pass

    def setAccessibleName(self, _value):
        pass

    def setToolTip(self, _value):
        pass

    def setStyleSheet(self, _value):
        pass

    def isChecked(self):
        return self._checked

    def setChecked(self, value):
        if value and self._group and self._group.exclusive:
            for button in self._group.buttons:
                button._checked = False
        self._checked = bool(value)

    def click(self):
        self.setChecked(True)
        self.clicked.emit(True)


class _ButtonGroup:
    def __init__(self, _parent=None):
        self.exclusive = False
        self.buttons = []

    def setExclusive(self, value):
        self.exclusive = bool(value)

    def addButton(self, button):
        self.buttons.append(button)
        button._group = self


class _Tabs:
    def __init__(self, titles):
        self.titles = list(titles)
        self.index = 0
        self.currentChanged = _Signal()

    def count(self):
        return len(self.titles)

    def tabText(self, index):
        return self.titles[index]

    def currentIndex(self):
        return self.index

    def setCurrentIndex(self, index):
        if self.index != index:
            self.index = index
            self.currentChanged.emit(index)


def _load_navigation_without_qt():
    pyside = ModuleType('PySide6')
    pyside.__path__ = []
    core = ModuleType('PySide6.QtCore')
    core.Qt = SimpleNamespace(TextElideMode=SimpleNamespace(ElideRight=1))
    gui = ModuleType('PySide6.QtGui')
    gui.QTextCursor = SimpleNamespace(MoveOperation=SimpleNamespace(Start=0))
    widgets = ModuleType('PySide6.QtWidgets')
    for name, value in {
        'QButtonGroup': _ButtonGroup, 'QCheckBox': _Button, 'QComboBox': _ComboBox,
        'QHBoxLayout': _Layout, 'QLabel': _Button, 'QPushButton': _Button,
        'QTabBar': _TabBar, 'QVBoxLayout': _Layout, 'QWidget': _Widget,
    }.items():
        setattr(widgets, name, value)
    app_module = ModuleType('app')
    app_module.__path__ = []
    display = ModuleType('app.depot_review_display_v020_a6')
    display.readable_depot_review = lambda _row: ''
    groups = ModuleType('app.result_tabs_v020_a6')

    def grouped_result_titles(titles):
        present = tuple(titles)
        definition = (
            ('Oversikt', ('Oversikt', 'Arkivdeler')),
            ('Eksterne kontroller', ('Arkade 5', 'KDRS Query')),
            ('Rapporter og evidens', ('Depotrapporter',)),
            ('Faglig vurdering', ('Periodevurdering', 'Depotvurdering')),
        )
        return tuple((name, tuple(t for t in options if t in present))
                     for name, options in definition)

    groups.grouped_result_titles = grouped_result_titles
    mocks = {
        'PySide6': pyside,
        'PySide6.QtCore': core,
        'PySide6.QtGui': gui,
        'PySide6.QtWidgets': widgets,
        'app': app_module,
        'app.depot_review_display_v020_a6': display,
        'app.result_tabs_v020_a6': groups,
    }
    with patch.dict(sys.modules, mocks):
        namespace = {'__name__': 'test_review_navigation_a16_2', '__package__': 'gui_qt'}
        exec(compile(SOURCE.read_text(encoding='utf-8'), str(SOURCE), 'exec'), namespace)
    return namespace['CompactResultNavigation']


class A162AssessmentButtonsTests(unittest.TestCase):
    def test_source_compiles_and_keeps_original_pages(self):
        source = SOURCE.read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('tabs.currentChanged.connect(self.sync_from_original)', source)
        self.assertIn('self.tabs.setCurrentIndex(index)', source)
        self.assertIn("QCheckBox('Vis rå JSON'", source)
        for unwanted in ('removeTab(', 'insertTab(', 'setParent(', 'record_depot_review('):
            self.assertNotIn(unwanted, source)

    def _nav(self):
        titles = ('Oversikt', 'Arkivdeler', 'Arkade 5', 'KDRS Query',
                  'Depotrapporter', 'Periodevurdering', 'Depotvurdering')
        tabs = _Tabs(titles)
        nav = _load_navigation_without_qt()(tabs, None)
        return tabs, nav

    def test_review_group_shows_two_buttons_not_dropdown(self):
        tabs, nav = self._nav()
        self.assertFalse(nav._review_area.visible)
        self.assertTrue(nav._choice_area.visible)
        nav.group_tabs.setCurrentIndex(3)
        self.assertEqual(tabs.tabText(tabs.currentIndex()), 'Periodevurdering')
        self.assertTrue(nav._review_area.visible)
        self.assertFalse(nav._choice_area.visible)
        self.assertEqual(set(nav.review_buttons), {'Periodevurdering', 'Depotvurdering'})
        self.assertTrue(nav.review_buttons['Periodevurdering'].isChecked())
        self.assertFalse(nav.review_buttons['Depotvurdering'].isChecked())

    def test_button_click_changes_same_underlying_tab(self):
        tabs, nav = self._nav()
        nav.group_tabs.setCurrentIndex(3)
        nav.review_buttons['Depotvurdering'].click()
        self.assertEqual(tabs.tabText(tabs.currentIndex()), 'Depotvurdering')
        self.assertTrue(nav.review_buttons['Depotvurdering'].isChecked())
        self.assertFalse(nav.review_buttons['Periodevurdering'].isChecked())
        nav.review_buttons['Periodevurdering'].click()
        self.assertEqual(tabs.tabText(tabs.currentIndex()), 'Periodevurdering')
        self.assertTrue(nav.review_buttons['Periodevurdering'].isChecked())

    def test_programmatic_navigation_syncs_active_button(self):
        tabs, nav = self._nav()
        tabs.setCurrentIndex(tabs.titles.index('Depotvurdering'))
        self.assertEqual(nav.group_tabs.currentIndex(), 3)
        self.assertTrue(nav._review_area.visible)
        self.assertTrue(nav.review_buttons['Depotvurdering'].isChecked())
        tabs.setCurrentIndex(tabs.titles.index('Periodevurdering'))
        self.assertTrue(nav.review_buttons['Periodevurdering'].isChecked())

    def test_other_groups_keep_existing_dropdown(self):
        tabs, nav = self._nav()
        nav.group_tabs.setCurrentIndex(3)
        nav.review_buttons['Depotvurdering'].click()
        nav.group_tabs.setCurrentIndex(1)
        self.assertEqual(tabs.tabText(tabs.currentIndex()), 'Arkade 5')
        self.assertTrue(nav._choice_area.visible)
        self.assertFalse(nav._review_area.visible)
        self.assertEqual(nav.view_choice.currentData(), 'Arkade 5')
        nav.view_choice.setCurrentIndex(nav.view_choice.findData('KDRS Query'))
        self.assertEqual(tabs.tabText(tabs.currentIndex()), 'KDRS Query')

    def test_last_professional_view_restored(self):
        tabs, nav = self._nav()
        nav.group_tabs.setCurrentIndex(3)
        nav.review_buttons['Depotvurdering'].click()
        nav.group_tabs.setCurrentIndex(0)
        nav.group_tabs.setCurrentIndex(3)
        self.assertEqual(tabs.tabText(tabs.currentIndex()), 'Depotvurdering')
        self.assertTrue(nav.review_buttons['Depotvurdering'].isChecked())

    def test_navigation_is_read_only(self):
        src = SOURCE.read_text(encoding='utf-8')
        self.assertNotIn('.write_text(', src)
        self.assertNotIn('.write_bytes(', src)
        self.assertNotIn('save_depot_metadata(', src)
        self.assertNotIn('update_current_metadata(', src)


if __name__ == '__main__':
    unittest.main()
