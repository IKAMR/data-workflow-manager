"""a3.2: delayed result-side Qt layout must not access deleted C++ widgets.

Uses fake Qt objects so the shutdown race is repeatable on every Python CI
host, including ones without a graphical desktop or PySide6 installed.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


class Signal:
    def __init__(self):
        self.handlers = []

    def connect(self, handler):
        self.handlers.append(handler)

    def emit(self, *args):
        for callback in tuple(self.handlers):
            callback(*args)


class Timer:
    def __init__(self, parent):
        self.parent = parent
        self.timeout = Signal()
        self.starts = []
        self.single_shot = False
        self._valid = True

    def setSingleShot(self, value):
        self.single_shot = value

    def start(self, timeout):
        self.starts.append(timeout)


class Tabs:
    def __init__(self):
        self._valid = True
        self.currentChanged = Signal()
        self.accesses = 0

    def currentIndex(self):
        self.accesses += 1
        if not self._valid:
            raise RuntimeError('libshiboken: Internal C++ object already deleted')
        return 0

    def tabText(self, index):
        return 'PRONOM'


class TreeModel:
    def __init__(self):
        self.modelReset = Signal()
        self.rowsInserted = Signal()


class Tree:
    def __init__(self):
        self._valid = True
        self.itemSelectionChanged = Signal()
        self._model = TreeModel()
        self.widths = []
        self.modes = []

    def setMinimumWidth(self, width):
        self.minimum_width = width

    def model(self):
        return self._model

    def header(self):
        return SimpleNamespace(setSectionResizeMode=lambda index, mode: self.modes.append((index, mode)))

    def fontMetrics(self):
        return SimpleNamespace(horizontalAdvance=lambda value: len(value) * 7)

    def headerItem(self):
        return SimpleNamespace(text=lambda index: 'Uttrekk')

    def topLevelItemCount(self):
        return 0

    def setColumnWidth(self, index, width):
        self.widths.append((index, width))

    def currentItem(self):
        return None


class Browser:
    def __init__(self):
        self._valid = True
        self.lines = []
        self.clear_count = 0

    def setMinimumWidth(self, width):
        self.minimum_width = width

    def setLineWrapMode(self, value):
        self.line_wrap = value

    def setWordWrapMode(self, value):
        self.word_wrap = value

    def clear(self):
        self.clear_count += 1

    def setHtml(self, value):
        self.lines.append(value)


class Splitter:
    def __init__(self):
        self._valid = True
        self._sizes = [230, 250, 0]
        self.set_calls = []

    def sizes(self):
        return list(self._sizes)

    def setSizes(self, sizes):
        self.set_calls.append(list(sizes))
        self._sizes = list(sizes)


class Viewer:
    def __init__(self):
        self._valid = True
        self.destroyed = Signal()
        self.tabs = Tabs()
        self._trees = {'PRONOM': Tree()}
        self._a53_splitters = {'PRONOM': Splitter()}
        self._a53_browsers = {'PRONOM': Browser()}
        self._a53_mode_selectors = {'PRONOM': SimpleNamespace(_valid=True, currentIndex=lambda: 0)}
        self._pages = {'PRONOM': SimpleNamespace(findChildren=lambda klass: ())}
        self._a4_settings = SimpleNamespace(value=lambda key, default: default)
        self._a53_setting_layout = False


def import_with_qt_stub():
    root = Path(__file__).resolve().parents[1]
    qt = ModuleType('PySide6')
    qtcore = ModuleType('PySide6.QtCore')
    qtcore.QTimer = Timer
    qtgui = ModuleType('PySide6.QtGui')
    qtgui.QTextOption = SimpleNamespace(
        WrapMode=SimpleNamespace(WrapAtWordBoundaryOrAnywhere=object()))
    qtwidgets = ModuleType('PySide6.QtWidgets')
    qtwidgets.QHeaderView = SimpleNamespace(ResizeMode=SimpleNamespace(Interactive=object()))
    qtwidgets.QPushButton = type('QPushButton', (), {})
    qtwidgets.QTextEdit = SimpleNamespace(LineWrapMode=SimpleNamespace(WidgetWidth=object()))
    shiboken = ModuleType('shiboken6')
    shiboken.isValid = lambda item: getattr(item, '_valid', True)
    app = ModuleType('app')
    app.__path__ = [str(root / 'app')]
    evidence = ModuleType('app.result_side_evidence_v020_a6')
    evidence.readable_side_evidence = lambda value: str(value)
    gui = ModuleType('gui_qt')
    gui.__path__ = [str(root / 'gui_qt')]
    center = ModuleType('gui_qt.result_center_v018_a13')
    center.DETAIL_ROLE = 31
    center.PATH_ROLE = 32
    modules = {
        'PySide6': qt, 'PySide6.QtCore': qtcore, 'PySide6.QtGui': qtgui,
        'PySide6.QtWidgets': qtwidgets, 'shiboken6': shiboken,
        'app': app, 'app.result_side_evidence_v020_a6': evidence,
        'gui_qt': gui, 'gui_qt.result_center_v018_a13': center,
    }
    path = root / 'gui_qt' / 'result_side_layout_v020_a6.py'
    spec = importlib.util.spec_from_file_location('gui_qt._result_side_lifecycle_test', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class DelayedPanelShutdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = import_with_qt_stub()

    def test_schedule_is_coalesced_and_timer_owned_by_viewer(self):
        viewer = Viewer()
        panel = self.module.ResponsiveSideResultPanels(viewer)
        self.assertIs(panel._timer.parent, viewer)
        self.assertTrue(panel._timer.single_shot)
        self.assertEqual(panel._timer.starts, [0])
        viewer.tabs.currentChanged.emit(1)
        viewer._trees['PRONOM'].model().modelReset.emit()
        self.assertEqual(panel._timer.starts, [0])

    def test_deleted_tab_widget_never_accessed_on_delayed_timeout(self):
        viewer = Viewer()
        panel = self.module.ResponsiveSideResultPanels(viewer)
        viewer.tabs._valid = False
        panel._timer.timeout.emit()
        self.assertEqual(viewer.tabs.accesses, 0)
        self.assertFalse(panel._pending)

    def test_destroyed_viewer_never_schedules_or_renders_again(self):
        viewer = Viewer()
        panel = self.module.ResponsiveSideResultPanels(viewer)
        viewer._valid = False
        viewer.destroyed.emit(None)
        self.assertTrue(panel._disposed)
        self.assertIsNone(panel.viewer)
        panel._timer.timeout.emit()  # also safe if a queued callback somehow survives
        panel._schedule()
        panel._render_detail('PRONOM')
        self.assertEqual(panel._timer.starts, [0])

    def test_alive_viewer_still_resizes_and_renders(self):
        viewer = Viewer()
        panel = self.module.ResponsiveSideResultPanels(viewer)
        panel._timer.timeout.emit()
        self.assertEqual(viewer._a53_splitters['PRONOM'].set_calls,
                         [[245, 235, 0]])  # PRONOM's 51% default
        self.assertEqual(viewer._trees['PRONOM'].widths[0][0], 0)
        self.assertEqual(viewer._a53_browsers['PRONOM'].clear_count, 1)
        self.assertFalse(viewer._a53_setting_layout)

    def test_saved_manual_splitter_fraction_is_not_overwritten(self):
        viewer = Viewer()
        viewer._a4_settings = SimpleNamespace(value=lambda key, default: 'manual')
        panel = self.module.ResponsiveSideResultPanels(viewer)
        panel._timer.timeout.emit()
        self.assertEqual(viewer._a53_splitters['PRONOM'].set_calls, [])

    def test_invalid_tree_is_skipped_without_qt_calls(self):
        viewer = Viewer()
        panel = self.module.ResponsiveSideResultPanels(viewer)
        viewer._trees['PRONOM']._valid = False
        panel._timer.timeout.emit()
        self.assertEqual(viewer._trees['PRONOM'].widths, [])


if __name__ == '__main__':
    unittest.main()
