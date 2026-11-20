"""Regression for live multi-job Basic binding (no native Qt needed)."""
from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import ast
import runpy
import sys
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
GUI_SOURCE = ROOT / 'gui_qt' / 'main_v024_a1.py'
ENTRY_SOURCE = ROOT / 'gui_qt' / '__main__.py'


class _OldBasic:
    """The a1 tests use the v0.2.3 observable behavior as a fake superclass."""

    def __init__(self):
        self.api = SimpleNamespace(
            running=True,
            job_details=lambda job_id: SimpleNamespace(job=SimpleNamespace(status='Kjører')))
        self._basic_active = True
        self._active_id = 'JOB-001'
        self._basic_job_id = 'JOB-001'
        self._a8_live_job = 'JOB-002'
        self._basic_last_run_signal = None
        self._basic_last_run_message = ''
        self._basic_operation_fraction = None
        self._basic_operation_index = None
        self._v022_loading_job = False
        self._v022_draft = False
        self._worker = object()
        self.calls = []

    def _a8_process_run_event(self, event):
        if event.job_id == self._basic_job_id:
            self._basic_last_run_signal = time.monotonic()
            if event.message:
                self._basic_last_run_message = event.message
        self._a8_live_job = event.job_id
        self.calls.append(('run.event', event.job_id))

    def _load_basic_active_job(self):
        self.calls.append(('read.job', self._active_id))
        self._basic_job_id = self._active_id

    def _v022_refresh_selector(self, *, force=False):
        self.calls.append(('selector', self._active_id))

    def _a8_refresh_job_log(self, *, force=False):
        self.calls.append(('log', self._active_id))

    def _a8_restore_run_context(self, *, force=False):
        self.calls.append(('details', self._active_id))

    def _open_basic_run_details(self):
        self._active_id = self._basic_job_id  # v0.2.3 bug, before the a1 override
        return self._active_id


def _load_isolated_window():
    qt = ModuleType('PySide6')
    qtcore = ModuleType('PySide6.QtCore')
    qtcore.Qt = SimpleNamespace(Orientation=SimpleNamespace(Vertical='vertical'))
    qtcore.QTimer = SimpleNamespace(singleShot=lambda _ms, fn: fn())
    qtwidgets = ModuleType('PySide6.QtWidgets')
    qtwidgets.QSplitter = type('QSplitter', (), {})
    qtwidgets.QSizePolicy = SimpleNamespace(Policy=SimpleNamespace(Expanding='expanding'))
    previous = ModuleType('gui_qt.main_v023_a4')
    previous.DwmMainWindow = _OldBasic
    with patch.dict(sys.modules, {
        'PySide6': qt, 'PySide6.QtCore': qtcore,
        'PySide6.QtWidgets': qtwidgets, 'gui_qt.main_v023_a4': previous,
    }):
        return runpy.run_path(str(GUI_SOURCE))['DwmMainWindow']


class BasicCurrentJobTests(unittest.TestCase):
    def test_class_import_does_not_require_qtcore_in_headless_startup(self):
        # Pre-existing v0.2.2 startup regressions stub QtWidgets only;
        # import-time QtCore access would break GUI startup in those tests.
        old_module = ModuleType('gui_qt.main_v023_a4')
        old_module.DwmMainWindow = _OldBasic
        with patch.dict(sys.modules, {
            'PySide6': ModuleType('PySide6'),
            'PySide6.QtCore': None,
            'PySide6.QtWidgets': ModuleType('PySide6.QtWidgets'),
            'gui_qt.main_v023_a4': old_module,
        }):
            loaded = runpy.run_path(str(GUI_SOURCE))['DwmMainWindow']
            self.assertTrue(issubclass(loaded, _OldBasic))

    def test_new_batch_job_updates_main_details_and_log_with_no_joblist_mutation(self):
        widget = _load_isolated_window()()
        widget._a8_process_run_event(SimpleNamespace(
            kind='run.started', job_id='JOB-002', message='Starter kontroll'))
        self.assertEqual(widget._basic_job_id, 'JOB-002')
        self.assertEqual(widget._active_id, 'JOB-002')
        self.assertEqual(widget._basic_last_run_message, 'Starter kontroll')
        self.assertIsNotNone(widget._basic_last_run_signal)
        self.assertIn(('selector', 'JOB-002'), widget.calls)
        self.assertIn(('details', 'JOB-002'), widget.calls)
        self.assertIn(('log', 'JOB-002'), widget.calls)
        self.assertEqual(widget._open_basic_run_details(), 'JOB-002')

    def test_heartbeat_without_a_real_message_does_not_reset_signal_clock(self):
        widget = _load_isolated_window()()
        widget._a8_process_run_event(SimpleNamespace(
            kind='run.started', job_id='JOB-002', message='Startet'))
        initial = widget._basic_last_run_signal
        widget._a8_process_run_event(SimpleNamespace(
            kind='run.state', job_id='JOB-002', message=''))
        self.assertEqual(widget._basic_last_run_signal, initial)
        widget._a8_process_run_event(SimpleNamespace(
            kind='run.progress', job_id='JOB-002', message=''))
        self.assertEqual(widget._basic_last_run_signal, initial)
        widget._a8_process_run_event(SimpleNamespace(
            kind='run.log', job_id='JOB-002', message='Siegfried: 1000 filer'))
        self.assertGreaterEqual(widget._basic_last_run_signal, initial)
        self.assertEqual(widget._basic_last_run_message, 'Siegfried: 1000 filer')

    def test_unknown_job_does_not_overwrite_active_selection(self):
        widget = _load_isolated_window()()
        def details(job_id):
            if job_id != 'JOB-001':
                raise KeyError(job_id)
        widget.api.job_details = details
        widget._v024_show_running_job('JOB-999')
        self.assertEqual(widget._active_id, 'JOB-001')
        self.assertEqual(widget._basic_job_id, 'JOB-001')

    def test_expanding_details_use_native_vertical_splitter(self):
        source = GUI_SOURCE.read_text(encoding='utf-8')
        tree = ast.parse(source)
        self.assertIn('QSplitter', source)
        self.assertIn('splitterMoved', source)
        self.assertIn('restoreState', source)
        self.assertIn('setMaximumHeight(16777215)', source)
        self.assertIn('layout.removeWidget(old_splitter)', source)
        self.assertIn('main_v024_a1 import DwmMainWindow', ENTRY_SOURCE.read_text(encoding='utf-8'))
        self.assertEqual([n.name for n in tree.body if isinstance(n, ast.ClassDef)], ['DwmMainWindow'])


if __name__ == '__main__':
    unittest.main()
