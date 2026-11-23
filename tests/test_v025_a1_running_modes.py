"""v0.2.5-a1: a running job remains the same job through Basic/Advanced changes.

Qt-free regression of the real GUI subclass; native Windows/Qt smoke tests
are separately required before promoting the alpha.
"""
from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import runpy
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / 'gui_qt/main_v025_a1.py'
ENTRY = ROOT / 'gui_qt/__main__.py'


class _FakeAPI:
    def __init__(self):
        self.running = True
        self.jobs = [
            SimpleNamespace(job_id='JOB-001', status='Kjører'),
            SimpleNamespace(job_id='JOB-002', status='Klar'),
        ]
        self.active_job_id = 'JOB-001'
        self.saves = 0
        self.selects = 0

    def workspace(self):
        return SimpleNamespace(jobs=tuple(self.jobs), active_job_id=self.active_job_id)

    def job_details(self, job_id):
        return SimpleNamespace(job=next(j for j in self.jobs if j.job_id == job_id))

    def save_job_list(self):
        self.saves += 1
        raise AssertionError('Navigation must not save a running job')

    def select_job(self, _job_id):
        self.selects += 1
        raise AssertionError('Navigation must not select a different persisted job')


class _PreviousWindow:
    def __init__(self):
        self.api = _FakeAPI()
        self._worker = object()
        self._job_controls_running = True
        self._basic_active = True
        self._basic_job_id = 'JOB-001'
        self._active_id = 'JOB-001'
        self._a8_live_job = 'JOB-001'
        self.calls = []
        self.register_calls = 0
        self.refreshed = 0

    def _leave_basic(self):
        # Original multijob transition: incorrectly insists on re-registering
        # the running job and therefore refuses the mode switch.
        self.register_calls += 1
        if self.api.running:
            self.calls.append('blocked-save')
            return
        self._basic_active = False
        self.calls.append('original-leave')

    def _enter_basic(self):
        self._basic_active = True
        self.calls.append('original-enter')

    def _v024_show_running_job(self, job_id):
        self._active_id = job_id
        self._basic_job_id = job_id
        self.calls.append(('show-live-job', job_id))

    def _sync_basic_status(self):
        self.calls.append('refresh-progress')

    def _a8_process_run_event(self, event):
        self.calls.append(('run', event.kind, event.job_id))

    def _a9_process_subjob_event(self, event):
        self.calls.append(('subjob', event.kind, event.job_id))

    def _refresh(self, *, force=False):
        self.refreshed += 1


class _OriginalBasicWindow:
    def _leave_basic(self):
        self._basic_active = False
        self.calls.append('view-only-leave')


def _event(kind, job_id):
    return SimpleNamespace(kind=kind, job_id=job_id)


class RunningModeTests(unittest.TestCase):
    def setUp(self):
        parent = ModuleType('gui_qt.main_v024_a4')
        parent.DwmMainWindow = _PreviousWindow
        legacy = ModuleType('gui_qt.basic_main_v0111_a1')
        legacy.DwmMainWindow = _OriginalBasicWindow
        substitions = {
            'gui_qt.main_v024_a4': parent,
            'gui_qt.basic_main_v0111_a1': legacy,
        }
        patcher = patch.dict(sys.modules, substitions)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cls = runpy.run_path(str(GUI))['DwmMainWindow']
        self.widget = self.cls()

    def test_running_basic_to_advanced_is_read_only_and_does_not_stop_worker(self):
        w = self.widget
        worker = w._worker
        w._leave_basic()
        self.assertFalse(w._basic_active)
        self.assertEqual(w._active_id, 'JOB-001')
        self.assertIs(w._worker, worker)
        self.assertTrue(w.api.running)
        self.assertEqual(w.register_calls, 0)
        self.assertEqual((w.api.saves, w.api.selects), (0, 0))
        self.assertIn('view-only-leave', w.calls)

    def test_roundtrip_to_basic_preserves_live_job_and_progress(self):
        w = self.widget
        w._leave_basic()
        w._enter_basic()
        self.assertTrue(w._basic_active)
        self.assertEqual(w._basic_job_id, 'JOB-001')
        self.assertIn(('show-live-job', 'JOB-001'), w.calls)
        self.assertIn('refresh-progress', w.calls)
        self.assertEqual((w.api.saves, w.api.selects), (0, 0))

    def test_next_batch_job_start_updates_advanced_and_basic_display_not_storage(self):
        w = self.widget
        w._leave_basic()
        w.api.jobs[0].status = 'Ferdig'
        w.api.jobs[1].status = 'Kjører'
        w._a8_process_run_event(_event('run.started', 'JOB-002'))
        self.assertEqual(w._active_id, 'JOB-002')
        self.assertEqual(w._v025_live_job, 'JOB-002')
        self.assertGreater(w.refreshed, 0)
        w._enter_basic()
        self.assertEqual(w._basic_job_id, 'JOB-002')
        self.assertEqual(w.api.active_job_id, 'JOB-001')  # persisted identity unchanged
        self.assertEqual((w.api.saves, w.api.selects), (0, 0))

    def test_progress_or_started_event_can_restore_current_job_when_returning_to_basic(self):
        w = self.widget
        w._leave_basic()
        w.api.jobs[0].status = 'Ferdig'
        w.api.jobs[1].status = 'Kjører'
        w._a8_process_run_event(_event('run.progress', 'JOB-002'))
        w._enter_basic()
        self.assertEqual(w._basic_job_id, 'JOB-002')

    def test_an_unrelated_or_unknown_run_event_cannot_retarget_job(self):
        w = self.widget
        w._leave_basic()
        w._a8_process_run_event(_event('run.started', 'JOB-999'))
        self.assertEqual(w._active_id, 'JOB-001')
        self.assertNotEqual(getattr(w, '_v025_live_job', None), 'JOB-999')

    def test_subjob_start_tracks_job_without_adding_a_runner(self):
        w = self.widget
        w._leave_basic()
        w.api.jobs[0].status = 'Ferdig'
        w.api.jobs[1].status = 'Kjører'
        w._a9_process_subjob_event(_event('subjob.started', 'JOB-002'))
        self.assertEqual(w._v025_live_job, 'JOB-002')
        self.assertIsNotNone(w._worker)

    def test_idle_transition_retains_existing_registration_guards(self):
        w = self.widget
        w._worker = None
        w._job_controls_running = False
        w.api.running = False
        w._leave_basic()
        self.assertEqual(w.register_calls, 1)
        self.assertIn('original-leave', w.calls)

    def test_finished_run_clears_transient_tracking(self):
        w = self.widget
        w._a8_process_run_event(_event('run.started', 'JOB-001'))
        w._a8_process_run_event(_event('run.finished', 'JOB-001'))
        self.assertIsNone(w._v025_live_job)

    def test_real_entrypoint_selects_v025_without_removing_v024_milestones(self):
        text = ENTRY.read_text(encoding='utf-8')
        self.assertIn('DwmMainWindow = _A4Window', text)
        self.assertIn('from gui_qt.main_v025_a1 import DwmMainWindow as _V025A1Window', text)
        self.assertIn('DwmMainWindow = _V025A1Window', text)
        self.assertLess(text.index('DwmMainWindow = _A4Window'),
                        text.index('DwmMainWindow = _V025A1Window'))


if __name__ == '__main__':
    unittest.main()
