"""v0.2.4-a2: deterministic continuation/reset without Qt or an archive.

The fake base represents the established Work-first facade boundary; the
real application uses the same overridden method names and call signatures.
"""
from __future__ import annotations

from enum import Enum
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Lock
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import sys
import unittest

from app.job_run_actions_v024_a2 import can_reset, resume_option

ROOT = Path(__file__).resolve().parents[1]


class Status(str, Enum):
    READY = 'Klar'
    RUNNING = 'Kj\u00f8rer'
    WAITING = 'Venter ved kontrollpunkt'
    FAILED = 'Feil'
    OK = 'Ferdig'
    SKIPPED = 'Hoppet over'


class FakeJob:
    def __init__(self, name, *, status=Status.FAILED, cursor=4, total=17):
        self.job_id = name
        self.status = status
        self.next_operation_index = cursor
        self.workflow_ids = [f'op-{i+1}' for i in range(total)]
        self.checkpoint_after = ['op-4']
        self.progress = cursor / total if total else 0
        self.message = 'Workflow stoppet med feil'
        self.log_entries = ['Tidligere kj\u00f8ring bevart']

    def has_checkpoint(self, operation_id):
        return operation_id in self.checkpoint_after

    def reset_execution(self, message=''):
        self.next_operation_index = 0
        self.progress = 0.0
        self.status = Status.READY
        self.message = message


class Error(Exception):
    pass


class FakeWorkbench:
    def __init__(self):
        self._guard = Lock()
        self._dirty = False
        self._active_job_id = 'JOB-002'
        self._path = '/original-joblist.n5jobs'
        self._work_references = {'JOB-001': '/trusted/work/job.json',
                                 'JOB-002': '/other/work/job.json'}
        self._unavailable_work_ids = frozenset()
        self.jobs = {'JOB-001': FakeJob('JOB-001'),
                     'JOB-002': FakeJob('JOB-002', status=Status.OK, cursor=17)}
        self.calls = []
        self.events = []
        self.fail_work_write = False
        self.fail_index = False
        self.preflight = SimpleNamespace(errors=[], actions=[], warnings=[])
        self.running = False

    def _assert_idle(self):
        if self.running:
            raise Error('Busy')

    def _require_job(self, job_id):
        if job_id not in self.jobs:
            raise Error('Unknown job')
        return self.jobs[job_id]

    def preflight_job(self, job_id):
        self.calls.append(('preflight', job_id))
        return self.preflight

    def _persist_work_event(self, job, kind='', detail=''):
        if self.fail_work_write:
            raise Error('Work write failed')
        self.events.append((kind, job.job_id, job.status, job.next_operation_index, detail))

    def _emit(self, kind, job=None, message='', progress=None):
        self.events.append(('emit', kind, job.job_id if job else None, message))

    def save_job_list(self):
        if self.fail_index:
            raise OSError('Joblist index offline')
        self._dirty = False
        self.calls.append(('save',))

    def job_details(self, job_id):
        job = self.jobs[job_id]
        return SimpleNamespace(job=SimpleNamespace(job_id=job_id,
                                                    status=job.status.value,
                                                    current_operation=job.next_operation_index,
                                                    operation_count=len(job.workflow_ids),
                                                    progress=job.progress),
                               message=job.message,
                               operations=tuple(SimpleNamespace(checkpoint=n in (4,))
                                                for n in range(1, len(job.workflow_ids)+1)))

    def run_job(self, job_id, *, allow_rerun=False, continue_waiting=False,
                acknowledge_warnings=False):
        job = self._require_job(job_id)
        self.calls.append(('run', job_id, allow_rerun, continue_waiting,
                           acknowledge_warnings, job.status, job.next_operation_index))
        return True


def load_api_class():
    module_name = 'dwm_v024_a2_api_test_only'
    app = ModuleType('app.application_api')
    app.DwmApiError = Error
    core = ModuleType('noark5_workflow.core.job')
    core.JobStatus = Status
    base = ModuleType('app.workbench_api_v020_a2')
    base.DwmWorkbenchAPI = FakeWorkbench
    with patch.dict(sys.modules, {'app.application_api': app,
                                  'noark5_workflow.core.job': core,
                                  'app.workbench_api_v020_a2': base}):
        spec = spec_from_file_location(module_name, ROOT / 'app/workbench_api_v024_a2.py')
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    return module.DwmWorkbenchAPI


class PolicyTests(unittest.TestCase):
    def test_failed_siegfried_cursor_retries_operation_five_not_one_or_six(self):
        o = resume_option(status='Feil', cursor=4, total=17)
        self.assertTrue(o.allowed)
        self.assertEqual((o.mode, o.position, o.total), ('failed_operation', 5, 17))

    def test_failed_first_operation_is_retryable_not_skipped(self):
        o = resume_option(status=Status.FAILED, cursor=0, total=17)
        self.assertEqual((o.mode, o.position), ('failed_operation', 1))

    def test_checkpoint_requires_real_prior_checkpoint(self):
        self.assertFalse(resume_option(status=Status.WAITING, cursor=4, total=17).allowed)
        o = resume_option(status=Status.WAITING, cursor=4, total=17,
                          previous_checkpoint=True)
        self.assertEqual((o.mode, o.position), ('checkpoint', 5))

    def test_partial_ready_has_its_own_resume_mode(self):
        self.assertEqual(resume_option(status=Status.READY, cursor=4, total=17).mode,
                         'partial_ready')
        self.assertFalse(resume_option(status=Status.READY, cursor=0, total=17).allowed)

    def test_invalid_cursor_never_starts_from_beginning_silently(self):
        for cursor in (-1, 17, 40, None):
            with self.subTest(cursor=cursor):
                self.assertFalse(resume_option(status='Feil', cursor=cursor,
                                               total=17).allowed)

    def test_disconnected_or_changed_job_never_continues(self):
        self.assertFalse(resume_option(status='Frakoblet (sist: Feil)',
                                       cursor=4, total=17).allowed)
        self.assertFalse(resume_option(status='Klar', cursor=4, total=17,
                                       message='Konfigurasjon endret - klar for ny kj\u00f8ring').allowed)

    def test_reset_requires_idle_and_prior_execution(self):
        self.assertTrue(can_reset(status='Feil', cursor=4))
        self.assertTrue(can_reset(status='Ferdig', cursor=17))
        self.assertTrue(can_reset(status='Klar', cursor=3))
        self.assertFalse(can_reset(status='Klar', cursor=0))
        self.assertFalse(can_reset(status='Kj\u00f8rer', cursor=4))
        self.assertFalse(can_reset(status='Frakoblet (sist: Feil)', cursor=4))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.api = load_api_class()()

    def test_continue_failed_keeps_cursor_work_history_and_other_job(self):
        untouched = self.api.jobs['JOB-002']
        self.assertTrue(self.api.run_job('JOB-001', continue_waiting=True,
                                         acknowledge_warnings=True))
        job = self.api.jobs['JOB-001']
        self.assertEqual((job.status, job.next_operation_index), (Status.READY, 4))
        self.assertEqual(job.log_entries, ['Tidligere kj\u00f8ring bevart'])
        self.assertIs(self.api.jobs['JOB-002'], untouched)
        self.assertEqual(untouched.status, Status.OK)
        self.assertIn(('run', 'JOB-001', False, False, True, Status.READY, 4), self.api.calls)
        self.assertEqual([r[0] for r in self.api.events], ['job.resume_requested'])

    def test_continue_waiting_preserves_original_checkpoint_path(self):
        job = self.api.jobs['JOB-001']
        job.status = Status.WAITING
        self.assertTrue(self.api.run_job('JOB-001', continue_waiting=True))
        self.assertEqual(self.api.calls[-1][3], True)
        self.assertEqual(self.api.calls[-1][-2], Status.WAITING)
        self.assertEqual(self.api.events, [])

    def test_failed_without_work_identity_is_not_restarted(self):
        self.api._work_references = {}
        job = self.api.jobs['JOB-001']
        with self.assertRaisesRegex(Error, 'Work-historikk'):
            self.api.run_job('JOB-001', continue_waiting=True)
        self.assertEqual((job.status, job.next_operation_index), (Status.FAILED, 4))
        self.assertFalse(any(r[0] == 'run' for r in self.api.calls))

    def test_bad_cursor_is_rejected_before_mutation(self):
        job = self.api.jobs['JOB-001']
        job.next_operation_index = 18
        with self.assertRaisesRegex(Error, 'Fortsett er ikke tilgjengelig'):
            self.api.run_job('JOB-001', continue_waiting=True)
        self.assertEqual(job.status, Status.FAILED)

    def test_failed_retry_aborts_without_change_if_preflight_blocks(self):
        job = self.api.jobs['JOB-001']
        self.api.preflight = SimpleNamespace(errors=[SimpleNamespace(message='Source missing')],
                                             actions=[], warnings=[])
        with self.assertRaisesRegex(Error, 'Source missing'):
            self.api.run_job('JOB-001', continue_waiting=True)
        self.assertEqual((job.status, job.next_operation_index), (Status.FAILED, 4))

    def test_failed_retry_rollback_when_work_write_fails(self):
        self.api.fail_work_write = True
        with self.assertRaisesRegex(Error, 'Work write failed'):
            self.api.run_job('JOB-001', continue_waiting=True)
        self.assertEqual(self.api.jobs['JOB-001'].status, Status.FAILED)
        self.assertFalse(any(c[0] == 'run' for c in self.api.calls))

    def test_partial_ready_uses_core_partial_cursor_without_checkpoint(self):
        job = self.api.jobs['JOB-001']
        job.status = Status.READY
        self.assertTrue(self.api.run_job('JOB-001', continue_waiting=True))
        self.assertEqual(self.api.calls[-1][-2:], (Status.READY, 4))
        self.assertEqual(self.api.calls[-1][3], False)

    def test_normal_rerun_is_still_an_independent_explicit_action(self):
        self.assertTrue(self.api.run_job('JOB-001', allow_rerun=True))
        self.assertEqual(self.api.jobs['JOB-001'].status, Status.FAILED)
        self.assertEqual(self.api.calls[-1][2:4], (True, False))

    def test_reset_persists_and_keeps_results_and_other_jobs(self):
        self.api.reset_job_execution('JOB-001')
        job = self.api.jobs['JOB-001']
        self.assertEqual((job.status, job.next_operation_index, job.progress),
                         (Status.READY, 0, 0.0))
        self.assertEqual(job.log_entries, ['Tidligere kj\u00f8ring bevart'])
        self.assertEqual(self.api.jobs['JOB-002'].status, Status.OK)
        self.assertEqual(self.api._active_job_id, 'JOB-001')
        self.assertIn('job.execution_reset', [event[0] for event in self.api.events])
        self.assertIn(('save',), self.api.calls)

    def test_reset_blocked_when_work_is_offline_or_job_running(self):
        self.api._unavailable_work_ids = frozenset({'JOB-001'})
        with self.assertRaisesRegex(Error, 'frakoblet'):
            self.api.reset_job_execution('JOB-001')
        self.api._unavailable_work_ids = frozenset()
        self.api.jobs['JOB-001'].status = Status.RUNNING
        with self.assertRaisesRegex(Error, 'ingen kj'):
            self.api.reset_job_execution('JOB-001')

    def test_reset_work_failure_rolls_back_in_memory_state(self):
        self.api.fail_work_write = True
        with self.assertRaisesRegex(Error, 'Work write failed'):
            self.api.reset_job_execution('JOB-001')
        job = self.api.jobs['JOB-001']
        self.assertEqual((job.status, job.next_operation_index, job.progress),
                         (Status.FAILED, 4, 4/17))
        self.assertEqual(self.api._active_job_id, 'JOB-002')

    def test_offline_joblist_does_not_undo_authoritative_work_reset(self):
        self.api.fail_index = True
        self.api.reset_job_execution('JOB-001')
        self.assertEqual(self.api.jobs['JOB-001'].status, Status.READY)
        self.assertIn('kunne ikke oppdateres', self.api._v024_a2_reset_index_warning)
        self.assertTrue(self.api._dirty)


if __name__ == '__main__':
    unittest.main()
