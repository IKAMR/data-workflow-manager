"""v0.2.4-a3: GUI startup-safe local popup observer and Work-first autosave.

Pure Python tests are intentional: native Windows placement requires an
additional real PySide6 test, while the permanent contracts can run in CI.
"""
from __future__ import annotations

import ast
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Lock
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FakeA2Api:
    def __init__(self):
        self._path = 'I:/test/jobs.n5jobs'
        self._work_references = {'JOB-001': 'I:/work/job.json'}
        self._work_index_warning = ''
        self._dirty = True
        self.calls = []
        self.raise_work = False
        self.fail_index = False

    def _persist_updated_job(self, job, job_id):
        self.calls.append(('persist_work_then_index', job_id))
        if self.raise_work:
            raise RuntimeError('Work storage unavailable')
        self._work_index_warning = ('Index write failed' if self.fail_index else '')


def load_class_without_parent_deps(path: Path, stub_import: str, parent):
    stub = ModuleType(stub_import)
    stub.DwmWorkbenchAPI = parent
    stub.DwmMainWindow = parent
    with patch.dict(sys.modules, {stub_import: stub}):
        spec = spec_from_file_location('dwm_a3_test_' + path.stem, path)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    return getattr(module, 'DwmWorkbenchAPI', None) or module.DwmMainWindow


class WorkFirstDirtyState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api_class = load_class_without_parent_deps(
            ROOT / 'app/workbench_api_v024_a3.py',
            'app.workbench_api_v024_a2', FakeA2Api,
        )

    def test_successful_work_and_index_write_clears_dirty(self):
        api = self.api_class()
        api._persist_updated_job(SimpleNamespace(job_id='JOB-001'), 'JOB-001')
        self.assertFalse(api._dirty)
        self.assertEqual(api.calls, [('persist_work_then_index', 'JOB-001')])

    def test_work_write_exception_keeps_dirty_and_is_not_silenced(self):
        api = self.api_class()
        api.raise_work = True
        with self.assertRaisesRegex(RuntimeError, 'Work storage unavailable'):
            api._persist_updated_job(SimpleNamespace(job_id='JOB-001'), 'JOB-001')
        self.assertTrue(api._dirty)

    def test_failed_joblist_index_keeps_dirty(self):
        api = self.api_class()
        api.fail_index = True
        api._persist_updated_job(SimpleNamespace(job_id='JOB-001'), 'JOB-001')
        self.assertTrue(api._dirty)

    def test_not_saved_when_no_index_path_or_work_identity(self):
        api = self.api_class()
        api._path = None
        api._persist_updated_job(SimpleNamespace(job_id='JOB-001'), 'JOB-001')
        self.assertTrue(api._dirty)
        api._path = 'I:/jobs.n5jobs'
        api._work_references = {}
        api._persist_updated_job(SimpleNamespace(job_id='JOB-001'), 'JOB-001')
        self.assertTrue(api._dirty)


class Point:
    def __init__(self, x, y):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y

    def __eq__(self, other):
        return isinstance(other, Point) and (self._x, self._y) == (other._x, other._y)


class FakeScreen:
    def availableGeometry(self):
        return SimpleNamespace(x=lambda: 0, y=lambda: 0,
                               width=lambda: 1920, height=lambda: 1080)


class FakeWidget:
    def __init__(self, parent=None, *, pos=(0, 0), size=(350, 40),
                 window=False, popup=False, visible=True):
        self._parent = parent
        self._pos = Point(*pos)
        self._size = size
        self._window = window
        self._popup = popup
        self._visible = visible
        self._properties = {}
        self.install_count = 0
        self.event_filter = None
        self.moves = 0
        self.on_move = None
        self._children = []
        if parent is not None:
            parent._children.append(self)

    def parentWidget(self):
        return self._parent

    def findChildren(self, cls):
        found = []
        for item in self._children:
            if isinstance(item, cls):
                found.append(item)
            found += item.findChildren(cls)
        return found

    def window(self):
        node = self
        while node is not None and not node._window:
            node = node._parent
        return node or self

    def isWindow(self):
        return self._window

    def windowFlags(self):
        return int(self._popup)

    def isVisible(self):
        return self._visible

    def property(self, key):
        return self._properties.get(key)

    def setProperty(self, key, value):
        self._properties[key] = value

    def installEventFilter(self, obj):
        self.install_count += 1
        self.event_filter = obj

    def width(self):
        return self._size[0]

    def height(self):
        return self._size[1]

    def mapToGlobal(self, point):
        return Point(self._pos.x() + point.x(), self._pos.y() + point.y())

    def layoutDirection(self):
        return 0

    def screen(self):
        return FakeScreen()

    def pos(self):
        return self._pos

    def move(self, point):
        self.moves += 1
        self._pos = point
        if self.on_move:
            self.on_move()


class FakeCombo(FakeWidget):
    def view(self):
        if not hasattr(self, 'popup'):
            self.popup = FakeWidget(parent=self, pos=(400, 720), size=(350, 100),
                                    window=True, popup=True)
        return SimpleNamespace(window=lambda: self.popup)


class Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, old, now):
        for callback in self.callbacks:
            callback(old, now)


class FakeApplication:
    def __init__(self):
        self.focusChanged = Signal()
        self.installs = 0

    def installEventFilter(self, _filter):
        self.installs += 1

    def focusWidget(self):
        return None


class PopupLocalTests(unittest.TestCase):
    def setUp(self):
        from gui_qt.combobox_anchor_v024_a3 import install_local_dropdown_anchors
        self.install = install_local_dropdown_anchors
        self.timers = []
        core = ModuleType('PySide6.QtCore')
        class QObject:
            def __init__(self, parent=None):
                self.parent = parent
        core.QObject = QObject
        core.QPoint = Point
        core.QEvent = SimpleNamespace(Type=SimpleNamespace(Show=17, Move=13, Resize=14))
        core.QTimer = SimpleNamespace(singleShot=lambda ms, fn: self.timers.append((ms, fn)))
        core.Qt = SimpleNamespace(WindowType=SimpleNamespace(Popup=1),
                                  LayoutDirection=SimpleNamespace(RightToLeft=1))
        widgets = ModuleType('PySide6.QtWidgets')
        widgets.QComboBox = FakeCombo
        widgets.QWidget = FakeWidget
        gui = ModuleType('PySide6.QtGui')
        gui.QGuiApplication = SimpleNamespace(screenAt=lambda point: FakeScreen())
        self.patcher = patch.dict(sys.modules, {'PySide6': ModuleType('PySide6'),
                                               'PySide6.QtCore': core,
                                               'PySide6.QtWidgets': widgets,
                                               'PySide6.QtGui': gui})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.app = FakeApplication()
        self.root = FakeWidget(window=True)
        self.combo = FakeCombo(parent=self.root, pos=(240, 255), size=(500, 35))
        self.install(self.app, self.root)
        self.filter = self.app._dwm_local_combo_anchor_v024_a3

    def test_no_app_wide_event_filter_and_idempotent_install(self):
        self.install(self.app, self.root)
        self.assertEqual(self.app.installs, 0)
        self.assertEqual(len(self.app.focusChanged.callbacks), 1)
        self.assertFalse(hasattr(self.combo, 'popup'), 'Must not create Qt popups at startup')

    def test_initial_and_delayed_native_move_are_corrected(self):
        popup = self.combo.view().window()
        self.app.focusChanged.emit(None, self.combo)
        self.assertEqual(popup.install_count, 1)
        event = SimpleNamespace(type=lambda: 17)
        popup.event_filter.eventFilter(popup, event)
        self.assertEqual(popup.pos(), Point(240, 290))
        popup._pos = Point(319, 660)
        popup.event_filter.eventFilter(popup, SimpleNamespace(type=lambda: 13))
        self.assertEqual(popup.pos(), Point(240, 290))
        for _delay, callback in self.timers:
            callback()
        self.assertEqual(popup.pos(), Point(240, 290))

    def test_does_not_loop_on_own_move_or_reinstall_for_same_combo(self):
        popup = self.combo.view().window()
        self.app.focusChanged.emit(None, self.combo)
        popup.on_move = lambda: popup.event_filter.eventFilter(
            popup, SimpleNamespace(type=lambda: 13))
        popup.event_filter.eventFilter(popup, SimpleNamespace(type=lambda: 13))
        self.assertEqual(popup.moves, 1)
        self.app.focusChanged.emit(None, self.combo)
        self.assertEqual(popup.install_count, 1)

    def test_future_dialog_combos_are_registered(self):
        dialog = FakeWidget(window=True)
        other = FakeCombo(parent=dialog, pos=(170, 440))
        self.app.focusChanged.emit(self.combo, other)
        self.assertEqual(other.view().window().install_count, 1)
        self.assertEqual(self.app.installs, 0)

    def test_other_popups_not_anchored(self):
        menu = FakeWidget(parent=self.root, window=True, popup=True, pos=(700, 700))
        self.filter.eventFilter(menu, SimpleNamespace(type=lambda: 13))
        self.assertEqual(menu.moves, 0)
        self.assertEqual(menu.install_count, 0)


class DistributionAndStartupTests(unittest.TestCase):
    def test_versions_match_and_a2_contracts_remain(self):
        version = (ROOT / 'version.py').read_text(encoding='utf-8')
        project = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
        self.assertIn('0.2.4-a3', version)
        self.assertIn('0.2.4a3', project)
        entry = (ROOT / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        self.assertIn('from gui_qt.main_v024_a2 import DwmMainWindow as _A2Window', entry)
        self.assertIn('from gui_qt.main_v024_a3 import DwmMainWindow as _A3Window', entry)
        self.assertIn('from app.workbench_api_v024_a3 import DwmWorkbenchAPI as _A3WorkbenchAPI', entry)
        self.assertIn('if features.popup_filter:', entry)
        self.assertLess(entry.index('from gui_qt.main_v024_a2'),
                        entry.index('from gui_qt.main_v024_a3'))

    def test_new_gui_has_no_module_level_qt_dependency(self):
        path = ROOT / 'gui_qt/main_v024_a3.py'
        for node in ast.parse(path.read_text(encoding='utf-8')).body:
            if isinstance(node, ast.ImportFrom):
                self.assertFalse(str(node.module).startswith('PySide6'))
        src = path.read_text(encoding='utf-8')
        self.assertIn("DWM_SAFE_MODE", src)


if __name__ == '__main__':
    unittest.main()
