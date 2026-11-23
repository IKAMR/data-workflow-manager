"""v0.2.5-a3: combined continuation and remaining jobs (Qt-free)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import runpy
import sys
import unittest

from app.batch_continue_v025_a3 import batch_can_advance, plan_remaining_jobs

ROOT = Path(__file__).resolve().parents[1]
GUI_FILE = ROOT / 'gui_qt/main_v025_a3.py'


@dataclass
class Job:
    job_id: str
    name: str
    status: str
    current_operation: int
    operation_count: int = 17
    progress: float = 0.0


@dataclass
class Resume:
    mode: str
    index: int
    total: int = 17
    allowed: bool = True
    reason: str = ''


class FakeAPI:
    def __init__(self, jobs):
        self.jobs = list(jobs)
        self.options = {}
        self.messages = {}
        self.running = False
        self.reads = []
        self.path = 'three-jobs.n5jobs'

    def workspace(self):
        return SimpleNamespace(jobs=tuple(self.jobs), job_list_path=self.path)

    def job_details(self, job_id):
        self.reads.append(('details', job_id))
        return SimpleNamespace(message=self.messages.get(job_id, ''))

    def resume_option_for_job(self, job_id):
        self.reads.append(('resume', job_id))
        return self.options.get(job_id, Resume('failed_operation', 5))

    def plan(self):
        return plan_remaining_jobs(self.jobs, details_for=self.job_details,
                                   resume_for=self.resume_option_for_job)


def example():
    api = FakeAPI([
        Job('JOB-001', 'Ferdig jobb', 'Ferdig', 17, progress=1),
        Job('JOB-002', 'Feilet A170', 'Feil', 5, progress=5/17),
        Job('JOB-003', 'Ny jobb', 'Klar', 0),
    ])
    api.options['JOB-002'] = Resume('failed_operation', 5)
    return api


class PlanTests(unittest.TestCase):
    def test_one_batch_continues_job_two_and_starts_job_three(self):
        api = example()
        before = tuple((j.job_id, j.status, j.current_operation, j.progress)
                       for j in api.jobs)
        plan = api.plan()
        self.assertTrue(plan.runnable)
        self.assertEqual(plan.completed, ('JOB-001',))
        self.assertEqual(plan.targets, [
            ('JOB-002', False, True), ('JOB-003', False, False)])
        self.assertEqual([s.position for s in plan.steps], [6, 1])
        self.assertIn('6/17', plan.steps[0].description)
        self.assertEqual(before, tuple((j.job_id, j.status, j.current_operation, j.progress)
                                       for j in api.jobs))
        self.assertNotIn(('resume', 'JOB-001'), api.reads)

    def test_several_partials_and_checkpoint_keep_list_order(self):
        api = FakeAPI([
            Job('one', 'Completed', 'Ferdig', 17, progress=1),
            Job('two', 'Failed', 'Feil', 5, progress=5/17),
            Job('three', 'Partial', 'Klar', 8, progress=8/17),
            Job('four', 'Waiting', 'Venter ved kontrollpunkt', 10, progress=10/17),
            Job('five', 'Fresh', 'Klar', 0),
        ])
        api.options = {
            'two': Resume('failed_operation', 5),
            'three': Resume('partial_ready', 8),
            'four': Resume('checkpoint', 10),
        }
        plan = api.plan()
        self.assertTrue(plan.runnable)
        self.assertEqual(plan.targets, [
            ('two', False, True), ('three', False, True),
            ('four', False, True), ('five', False, False)])
        self.assertEqual([s.position for s in plan.steps], [6, 9, 11, 1])

    def test_no_auto_rerun_of_completed_and_all_completed_is_not_runnable(self):
        api = FakeAPI([Job('one', 'one', 'Ferdig', 17, progress=1)])
        plan = api.plan()
        self.assertEqual(plan.targets, [])
        self.assertFalse(plan.runnable)

    def test_unknown_skipped_running_disconnected_block_the_whole_request(self):
        api = example()
        api.jobs.append(Job('JOB-004', 'Skipped', 'Hoppet over', 8, progress=8/17))
        plan = api.plan()
        self.assertFalse(plan.runnable)
        self.assertEqual([v.job_id for v in plan.blocked], ['JOB-004'])
        api.jobs[-1].status = 'Frakoblet (sist: Feil)'
        self.assertFalse(api.plan().runnable)
        api.jobs[-1].status = 'Kjører'
        self.assertFalse(api.plan().runnable)

    def test_failed_without_verified_work_is_blocked_not_started_from_zero(self):
        api = example()
        api.options['JOB-002'] = Resume('', 0, allowed=False, reason='Mangler Work-historikk')
        plan = api.plan()
        self.assertFalse(plan.runnable)
        self.assertEqual(plan.blocked[0].reason, 'Mangler Work-historikk')
        self.assertEqual(plan.targets, [('JOB-003', False, False)])

    def test_wrong_checkpoint_or_cursor_is_never_trusted(self):
        api = FakeAPI([Job('x', 'x', 'Venter ved kontrollpunkt', 7, progress=7/17)])
        api.options['x'] = Resume('failed_operation', 7)
        self.assertFalse(api.plan().runnable)
        api.options['x'] = Resume('checkpoint', 6)
        self.assertFalse(api.plan().runnable)
        api.options['x'] = Resume('checkpoint', 7, total=18)
        self.assertFalse(api.plan().runnable)

    def test_strange_cursor_progress_or_missing_workflow_blocks(self):
        for cursor, progress, total in [(-1, 0, 17), (17, 0, 17), (0, 0, 0),
                                        (0, 0.4, 17), (0, float('nan'), 17),
                                        (None, 0, 17)]:
            with self.subTest(cursor=cursor, progress=progress, total=total):
                api = FakeAPI([Job('x', 'x', 'Klar', cursor, total, progress)])
                self.assertFalse(api.plan().runnable)

    def test_changed_configuration_needs_explicit_operator_action(self):
        api = FakeAPI([Job('x', 'x', 'Klar', 0)])
        api.messages['x'] = 'Konfigurasjon endret - klar for ny kjøring'
        self.assertFalse(api.plan().runnable)
        self.assertIn('konfigurasjon', api.plan().blocked[0].reason.lower())

    def test_duplicate_ids_block_entire_batch(self):
        api = FakeAPI([Job('x', 'x', 'Klar', 0), Job('x', 'y', 'Klar', 0)])
        self.assertFalse(api.plan().runnable)

    def test_checkpoint_does_not_auto_advance_into_next_job(self):
        self.assertTrue(batch_can_advance(True, 'Ferdig'))
        for status in ('Venter ved kontrollpunkt', 'Feil', 'Hoppet over', 'Kjører', None):
            self.assertFalse(batch_can_advance(True, status), status)
        self.assertFalse(batch_can_advance(False, 'Ferdig'))


class FakeWindow:
    def __init__(self, api):
        self.api = api
        self._worker = None
        self._job_controls_running = False
        self._basic_active = False
        self.calls = []
        # No _toolbar: simulate existing Qt-free GUI startup regressions.

    def _start_worker(self, targets):
        self.calls.append(('start', list(targets)))

    def _refresh(self, *args, **kwargs):
        return None

    def _sync_basic_status(self):
        return None

    def _set_running_ui(self, running):
        self._job_controls_running = running


class Messages:
    class StandardButton:
        Yes = 1
        No = 2
    result = 1
    ask = None
    details = []

    @classmethod
    def question(cls, _window, caption, body, *args):
        cls.details.append(('question', caption, body))
        if cls.ask:
            cls.ask()
        return cls.result

    @classmethod
    def warning(cls, _window, caption, body):
        cls.details.append(('warning', caption, body))

    @classmethod
    def information(cls, _window, caption, body):
        cls.details.append(('info', caption, body))


def gui_class():
    old = ModuleType('gui_qt.main_v025_a1')
    old.DwmMainWindow = FakeWindow
    pyqt = ModuleType('PySide6')
    qtwidgets = ModuleType('PySide6.QtWidgets')
    qtwidgets.QMessageBox = Messages
    with patch.dict(sys.modules, {'gui_qt.main_v025_a1': old,
                                  'PySide6': pyqt, 'PySide6.QtWidgets': qtwidgets}):
        return runpy.run_path(str(GUI_FILE))['DwmMainWindow']


class UiTests(unittest.TestCase):
    def setUp(self):
        Messages.result = Messages.StandardButton.Yes
        Messages.ask = None
        Messages.details = []
        qtwidgets = ModuleType('PySide6.QtWidgets')
        qtwidgets.QMessageBox = Messages
        self._qt_patch = patch.dict(sys.modules, {
            'PySide6': ModuleType('PySide6'), 'PySide6.QtWidgets': qtwidgets,
        })
        self._qt_patch.start()
        self.addCleanup(self._qt_patch.stop)
        self.api = example()
        self.gui = gui_class()(self.api)

    def test_single_confirmation_starts_one_shared_batch(self):
        self.gui._v025_a3_run_remaining()
        self.assertEqual(self.gui.calls, [('start', [
            ('JOB-002', False, True), ('JOB-003', False, False)])])
        self.assertEqual(len(Messages.details), 1)
        self.assertIn('5', str(self.api.jobs[1].current_operation))
        self.assertIn('6/17', Messages.details[0][2])
        self.assertIn('1/17', Messages.details[0][2])

    def test_no_confirmation_no_run(self):
        Messages.result = Messages.StandardButton.No
        self.gui._v025_a3_run_remaining()
        self.assertFalse(self.gui.calls)

    def test_stale_plan_between_confirmation_and_launch_is_rejected(self):
        def update():
            self.api.jobs[1].status = 'Ferdig'
        Messages.ask = update
        self.gui._v025_a3_run_remaining()
        self.assertFalse(self.gui.calls)
        self.assertEqual(Messages.details[-1][0], 'warning')

    def test_running_worker_refuses_double_start(self):
        self.gui._worker = object()
        self.gui._v025_a3_run_remaining()
        self.assertFalse(self.gui.calls)

    def test_unsaved_basic_metadata_is_not_silently_changed(self):
        self.gui._basic_active = True
        self.gui._a2_pending_dirty = True
        self.gui._v025_a3_run_remaining()
        self.assertFalse(self.gui.calls)
        self.assertEqual(Messages.details[-1][0], 'info')

    def test_blocked_job_causes_no_workers_even_if_others_are_ready(self):
        self.api.options['JOB-002'] = Resume('', 0, allowed=False, reason='Work frakoblet')
        self.gui._v025_a3_run_remaining()
        self.assertFalse(self.gui.calls)
        self.assertEqual(Messages.details[-1][0], 'warning')

    def test_gui_inheritance_and_versions_are_wired(self):
        self.assertTrue(issubclass(gui_class(), FakeWindow))
        # Also checked by the release test after the patch is applied to repo.
        self.assertTrue(GUI_FILE.is_file())


if __name__ == '__main__':
    unittest.main()
