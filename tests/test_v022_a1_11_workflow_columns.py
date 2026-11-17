"""Headless and simulated Qt-contract tests for a1.11 Advanced subjob columns."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from gui_qt.workflow_columns_v022_a1_11 import (
    DEFAULT_WIDTHS, MAX_WIDTH, PREFERENCE_KEY, column_widths,
    install_editable_workflow_columns, serialize_widths,
)


class Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in self.callbacks:
            callback(*args)


class Header:
    def __init__(self):
        self.widths = [100, 100, 100, 100]
        self.sectionResized = Signal()
        self.sectionDoubleClicked = Signal()
        self.mode = {}
        self.stretch = None
        self.movable = None
        self.min_section = None
        self.tooltip = None

    def setStretchLastSection(self, value):
        self.stretch = value

    def setSectionsMovable(self, value):
        self.movable = value

    def setMinimumSectionSize(self, value):
        self.min_section = value

    def setSectionResizeMode(self, index, mode):
        self.mode[index] = mode

    def resizeSection(self, index, width):
        old = self.widths[index]
        self.widths[index] = width
        if old != width:
            self.sectionResized.emit(index, old, width)

    def sectionSize(self, index):
        return self.widths[index]

    def setToolTip(self, tooltip):
        self.tooltip = tooltip


class FakeTree:
    def __init__(self):
        self._header = Header()
        self.itemEntered = Signal()
        self.scroll_policy = None
        self.elide_mode = None
        self.mouse_tracking = None
        self.fits = []

    def header(self):
        return self._header

    def setHorizontalScrollBarPolicy(self, policy):
        self.scroll_policy = policy

    def setTextElideMode(self, mode):
        self.elide_mode = mode

    def setMouseTracking(self, value):
        self.mouse_tracking = value

    def resizeColumnToContents(self, index):
        self.fits.append(index)
        self._header.resizeSection(index, 1600 if index == 1 else 110)


class FakeConfig:
    def __init__(self, stored=None):
        self.saved = {} if stored is None else {PREFERENCE_KEY: stored}

    def value(self, key, default=None):
        return self.saved.get(key, default)

    def setValue(self, key, value):
        self.saved[key] = value


class FakeWindow:
    def __init__(self, stored=None):
        self.workflow_tree = FakeTree()
        self.config = FakeConfig(stored)
        self.visible = False

    def isVisible(self):
        return self.visible


class FakeItem:
    def __init__(self):
        self.tooltip = 'metadata_inventory · Noark 5'

    def text(self, index):
        return 'Metadataoversikt' if index == 1 else ''

    def toolTip(self, index):
        return self.tooltip

    def setToolTip(self, index, text):
        self.tooltip = text


class TestColumns(unittest.TestCase):
    def test_defaults_and_invalid_preferences(self):
        for invalid in (None, '', '{', '[]', '[1, 2, 3]', '[1, true, 3, 4]',
                        (1, 2, 'x', 4), {}, [1, 2, 3]):
            with self.subTest(invalid=invalid):
                self.assertEqual(column_widths(invalid), DEFAULT_WIDTHS)

    def test_saved_widths_are_restored_and_safely_bounded(self):
        self.assertEqual(column_widths('[38, 440, 120, 85]'), (38, 440, 120, 85))
        self.assertEqual(column_widths([-100, 99999, 70, 65]),
                         (30, MAX_WIDTH, 70, 65))
        self.assertEqual(column_widths(serialize_widths([42, 620, 100, 70])),
                         (42, 620, 100, 70))

    def test_install_interactive_all_and_horizontal_scroll(self):
        window = FakeWindow()
        with self.fake_qt():
            self.assertTrue(install_editable_workflow_columns(window))
        header = window.workflow_tree.header()
        self.assertEqual(header.stretch, False)
        self.assertEqual(header.movable, False)
        self.assertEqual(list(header.mode.values()), ['Interactive'] * 4)
        self.assertEqual(tuple(header.widths), DEFAULT_WIDTHS)
        self.assertEqual(window.workflow_tree.scroll_policy, 'ScrollBarAsNeeded')
        self.assertIn('Dra kolonnegrensene', header.tooltip)
        self.assertEqual(window.config.saved, {})
        self.assertFalse(install_called_twice_changes_preferences(window))

    def test_dragging_and_double_click_resizes_and_persists(self):
        window = FakeWindow('[38,400,90,72]')
        with self.fake_qt():
            install_editable_workflow_columns(window)
            header = window.workflow_tree.header()
            self.assertEqual(tuple(header.widths), (38, 400, 90, 72))
            # Native show/layout adjustments should not overwrite saved values.
            header.resizeSection(1, 420)
            self.assertEqual(window.config.saved[PREFERENCE_KEY], '[38,400,90,72]')
            window.visible = True
            header.resizeSection(1, 500)
            self.assertEqual(json.loads(window.config.saved[PREFERENCE_KEY]), [38, 500, 90, 72])
            # Double-click a header divider: expand to text and cap the width.
            header.sectionDoubleClicked.emit(1)
            self.assertEqual(window.workflow_tree.fits, [1])
            self.assertEqual(header.sectionSize(1), MAX_WIDTH)
            self.assertEqual(json.loads(window.config.saved[PREFERENCE_KEY])[1], MAX_WIDTH)

    def test_full_operation_name_on_hover_preserves_operation_id(self):
        window = FakeWindow()
        with self.fake_qt():
            install_editable_workflow_columns(window)
        item = FakeItem()
        window.workflow_tree.itemEntered.emit(item, 1)
        self.assertEqual(item.tooltip, 'Metadataoversikt\nmetadata_inventory · Noark 5')
        window.workflow_tree.itemEntered.emit(item, 1)
        self.assertEqual(item.tooltip.count('Metadataoversikt'), 1)

    def test_a112_starts_without_optional_column_hook(self):
        # a1.12 recovery: a1.11's eager Qt hook is temporarily disabled.
        # Keep the independent column-logic tests above for a later re-enable.
        main = (Path(__file__).resolve().parents[1] / 'gui_qt' / '__main__.py').read_text(encoding='utf-8')
        created = main.index('window = DwmMainWindow(api)')
        integrated = main.index('install_integrated_home(window)')
        shown = main.index('    window.show()')
        self.assertLess(created, integrated)
        self.assertLess(integrated, shown)
        self.assertNotIn('install_editable_workflow_columns(window)', main)
        self.assertNotIn('from gui_qt.workflow_columns_v022_a1_11 import', main)

    @staticmethod
    def fake_qt():
        class CoreQt:
            class ScrollBarPolicy:
                ScrollBarAsNeeded = 'ScrollBarAsNeeded'
            class TextElideMode:
                ElideRight = 'ElideRight'
        class HeaderMode:
            Interactive = 'Interactive'
        class QHeaderView:
            ResizeMode = HeaderMode
        py = types.ModuleType('PySide6')
        core = types.ModuleType('PySide6.QtCore')
        core.Qt = CoreQt
        widgets = types.ModuleType('PySide6.QtWidgets')
        widgets.QHeaderView = QHeaderView
        return patch.dict(sys.modules, {'PySide6': py, 'PySide6.QtCore': core,
                                       'PySide6.QtWidgets': widgets})


def install_called_twice_changes_preferences(window):
    before = dict(window.config.saved)
    with TestColumns.fake_qt():
        result = install_editable_workflow_columns(window)
    return result or before != window.config.saved


if __name__ == '__main__':
    unittest.main()
