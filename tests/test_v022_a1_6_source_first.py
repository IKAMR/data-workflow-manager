"""v0.2.2-a1.6: Source-first Basic navigation and contextual extraction selector.

Qt-free fake-widget regression checks: the real PySide6 window remains a
Windows GUI acceptance test. No Source, Work, or job-list files are written.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
GUI = ROOT / 'gui_qt' / 'basic_multijob_v022_a1_2.py'


class Widget:
    def __init__(self, text=''):
        self.text_value = text
        self.visible = None
        self.enabled = None

    def setVisible(self, visible):
        self.visible = bool(visible)

    def setTitle(self, title):
        self.title = str(title)

    def hide(self):
        self.visible = False

    def show(self):
        self.visible = True

    def setText(self, text):
        self.text_value = str(text)

    def text(self):
        return self.text_value

    def setToolTip(self, text):
        self.tooltip = str(text)

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)


class Combo(Widget):
    def __init__(self):
        super().__init__()
        self.entries = []
        self.selected_index = -1

    def blockSignals(self, state):
        self.blocked = state

    def clear(self):
        self.entries.clear()

    def addItem(self, label, data):
        self.entries.append((label, data))

    def findData(self, data):
        for index, (_, item) in enumerate(self.entries):
            if item == data:
                return index
        return -1

    def setCurrentIndex(self, index):
        self.selected_index = index

    def currentData(self):
        if 0 <= self.selected_index < len(self.entries):
            return self.entries[self.selected_index][1]
        return None


class API:
    def __init__(self):
        self.jobs = []
        self.path = None
        self.running = False
        self.statuses = {}

    def workspace(self):
        return types.SimpleNamespace(
            job_list_path=self.path,
            jobs=tuple(types.SimpleNamespace(job_id=key, name=name,
                       status=self.statuses.get(key, 'Klar'), progress=0,
                       current_operation=0) for key, name in self.jobs),
        )


def load_gui_class():
    """Load the real extension class without a native display/Qt installation."""
    qt = types.ModuleType('PySide6')
    qt.__path__ = []
    qtcore = types.ModuleType('PySide6.QtCore')
    qtcore.Qt = object()
    widgets = types.ModuleType('PySide6.QtWidgets')
    for name in ('QComboBox', 'QGroupBox', 'QHBoxLayout', 'QLabel',
                 'QPushButton', 'QVBoxLayout'):
        setattr(widgets, name, type(name, (), {}))
    widgets.QMessageBox = type('QMessageBox', (), {})
    original = types.ModuleType('gui_qt.main_v020_a6')
    original.DwmMainWindow = type('OriginalDwmMainWindow', (), {
        '_a2_set_step': lambda self, step: setattr(self, '_a2_current_step', step),
    })
    with patch.dict(sys.modules, {'PySide6': qt, 'PySide6.QtCore': qtcore,
                                  'PySide6.QtWidgets': widgets,
                                  'gui_qt.main_v020_a6': original}):
        spec = importlib.util.spec_from_file_location('test_source_first_a16_gui', GUI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module.DwmMainWindow


class SourceFirstTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window_class = load_gui_class()

    def window(self):
        window = object.__new__(self.window_class)
        window.api = API()
        window._active_id = None
        window._v022_draft = True
        window._v022_selector_signature = None
        window._v022_save_failed = False
        window._worker = None
        window._a2_current_step = 'source'
        window.v022_registration_status = Widget()
        window.v022_selector_group = Widget()
        window.v022_job_selector = Combo()
        window.v022_selector_caption = Widget()
        window.v022_current_job_label = Widget()
        window.v022_joblist_status = Widget()
        window.v022_new_job_button = Widget()
        window.v022_save_job_button = Widget()
        window.v022_save_list_button = Widget()
        return window

    def test_navigation_is_linear_and_overview_optional_last(self):
        order = ('source', 'work', 'run', 'overview')
        for i, step in enumerate(order):
            self.assertEqual(self.window_class._a3_neighbor_step(
                step, 1), order[i + 1] if i + 1 < len(order) else None)
            self.assertEqual(self.window_class._a3_neighbor_step(
                step, -1), order[i - 1] if i > 0 else None)
        self.assertIsNone(self.window_class._a3_neighbor_step('bogus', 1))
        self.assertIsNone(self.window_class._a3_neighbor_step('source', 0))

    def test_zero_jobs_has_no_duplicate_chooser_or_save_bar(self):
        w = self.window()
        w._v022_refresh_selector(force=True)
        self.assertFalse(w.v022_selector_group.visible)
        self.assertEqual(w.v022_job_selector.entries, [('Nytt uttrekk – ikke registrert', None)])
        self.assertEqual(w.api.workspace().jobs, ())

    def test_one_existing_extraction_shows_summary_not_second_picker(self):
        w = self.window()
        w.api.jobs = [('JOB-001', 'content')]
        w.api.path = 'C:/work/jobs.n5jobs'
        w._active_id = 'JOB-001'
        w._v022_draft = False
        w._v022_refresh_selector(force=True)
        self.assertFalse(w.v022_selector_group.visible)  # no batch UI on Source
        w._a2_current_step = 'run'
        w._v022_refresh_selector(force=True)
        self.assertTrue(w.v022_selector_group.visible)
        self.assertTrue(w.v022_current_job_label.visible)
        self.assertFalse(w.v022_job_selector.visible)
        self.assertFalse(w.v022_selector_caption.visible)
        self.assertIn('JOB-001', w.v022_current_job_label.text())
        self.assertIn('Lagret i jobs.n5jobs', w.v022_joblist_status.text())
        self.assertIn('Registrert, ikke kjørt', w.v022_registration_status.text())

    def test_three_jobs_can_choose_any_and_draft_is_distinct(self):
        w = self.window()
        w.api.jobs = [('JOB-001', 'A'), ('JOB-002', 'B'), ('JOB-003', 'C')]
        w._active_id = 'JOB-002'
        w._v022_draft = False
        w._v022_refresh_selector(force=True)
        self.assertTrue(w.v022_selector_group.visible)
        self.assertTrue(w.v022_job_selector.visible)
        self.assertFalse(w.v022_current_job_label.visible)
        self.assertEqual(w.v022_job_selector.currentData(), 'JOB-002')
        self.assertEqual([key for _, key in w.v022_job_selector.entries],
                         ['JOB-001', 'JOB-002', 'JOB-003'])
        w._v022_draft = True
        w._v022_refresh_selector(force=True)
        self.assertEqual(w.v022_job_selector.currentData(), None)
        self.assertEqual([key for _, key in w.v022_job_selector.entries],
                         [None, 'JOB-001', 'JOB-002', 'JOB-003'])
        self.assertIn('velg Source og Work', w.v022_registration_status.text())

    def test_buttons_and_real_steps_are_reordered_without_new_fields(self):
        w = self.window()
        keys = ('overview', 'source', 'work', 'run')
        widgets = {key: Widget(key) for key in keys}

        class Navigation:
            def __init__(self):
                self.items = list(widgets.values()) + ['spacing', 'previous', 'next']
            def removeWidget(self, item):
                self.items.remove(item)
            def insertWidget(self, index, item, stretch):
                self.items.insert(index, item)

        class Group:
            def __init__(self):
                self.title = ''
            def setTitle(self, name):
                self.title = name
            def parentWidget(self):
                return self
            def findChildren(self, what):
                return []

        w._a2_navigation = Navigation()
        w._a2_step_buttons = widgets
        w._a2_step_groups = {key: Group() for key in ('source', 'work', 'run')}
        w._a2_current_step = 'overview'
        w._a2_set_step = lambda step: setattr(w, 'selected_step', step)
        w._v022_install_source_first_navigation()
        self.assertEqual([next(k for k, v in widgets.items() if v is item)
                          for item in w._a2_navigation.items[:4]],
                         ['source', 'work', 'run', 'overview'])
        self.assertEqual(w.selected_step, 'overview')
        self.assertIn('Velg arkivuttrekk', w._a2_step_groups['source'].title)
        self.assertIn('arbeidsmappe', w._a2_step_groups['work'].title)

    def test_source_first_applies_to_new_control_and_return_from_advanced(self):
        text = GUI.read_text(encoding='utf-8')
        ast.parse(text)
        self.assertIn("self._a2_set_step('source')", text)
        self.assertIn('basic_selector_visible(len(jobs), step', text)
        self.assertNotIn('self.api.dirty', text)
        # New control and adding one extraction are not the same command.
        tree = ast.parse(text)
        methods = {node.name: ast.get_source_segment(text, node)
                   for cls in tree.body if isinstance(cls, ast.ClassDef)
                   for node in cls.body if isinstance(node, ast.FunctionDef)}
        self.assertIn('self.api.new_job_list()', methods['_a3_new_control'])
        self.assertNotIn('self.api.new_job_list()', methods['_v022_new_draft'])
        self.assertIn('self._v022_register_current()', methods['_v022_new_draft'])


if __name__ == '__main__':
    unittest.main()
