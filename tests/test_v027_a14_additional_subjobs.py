"""a14: supplementary one-operation runs must not rewrite a finished job."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock, Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.additional_subjobs_v027_a14 import (
    SIEGFRIED, EXTRA_KEY, additional_ids, add_additional_subjob,
    extended_workflow, inspect_additional_subjob, run_additional_subjob,
)
from noark5_workflow.core.job import Job, JobStatus
from app.application_api import DwmApiError


HISTORIC_FLOW = (
    'metadata_inventory', 'validate_xml_schema', 'analyse_arkivstruktur',
    'arkade5_noark5_test', 'arkade5_pronom_analysis',
    'run_noark5_xpath_tests_2026', 'import_arkade5_reports',
    'build_noark5_canonical_evidence', 'analyze_noark5_external_evidence',
    'audit_noark5_evidence', 'compose_noark5_views',
    'build_noark5_depot_report', 'build_noark5_qa_draft',
)


class A14Api:
    def __init__(self, job, work, joblist):
        self.job = job
        self.work = work
        self._path = joblist
        self._guard = Lock()
        self._running = False
        self._cancel = Event()
        self._work_references = {job.job_id: work / 'job.json'}
        self._unavailable_work_ids = set()
        self.settings = {'sf_executable': ''}
        self._dirty = False
        self._a8_run_writer = None
        self._a8_log_warning = ''
        self.snapshots = []
        self.engine_jobs = []
        self.calls = []

    def _assert_idle(self):
        if self._running:
            raise DwmApiError('busy')

    def _require_job(self, job_id):
        if job_id != self.job.job_id:
            raise DwmApiError('unknown job')
        return self.job

    def _registry_catalog(self):
        from app.workflow_dependencies_v022_a7 import BY_ID
        return {key: (key, 'test') for key in BY_ID}

    def workspace(self):
        return SimpleNamespace(job_list_path=str(self._path), jobs=(
            SimpleNamespace(job_id=self.job.job_id, name=self.job.name,
                            effective_work_operations=self.work),
        ))

    def _inspect_job(self, job, *, operation_id=None):
        return SimpleNamespace(errors=(), actions=(), warnings=())

    def check_storage(self):
        return ()

    def _persist_work_event(self, job, kind, detail):
        self.snapshots.append((kind, tuple(job.workflow_ids),
                               job.status, job.next_operation_index))

    def save_job_list(self):
        self.calls.append('save')
        return self._path

    def _runner_factory(self, settings):
        api = self
        class Runner:
            def run_operation(self, job, operation_id, **callbacks):
                api.engine_jobs.append((job, operation_id, settings))
                callbacks['log_cb']('Executed ' + operation_id)
                callbacks['progress_cb'](0.5, 'In progress')
                callbacks['state_cb'](job)
                return SimpleNamespace(ok=True)
        return Runner()

    def _emit(self, kind, job, *, message='', progress=None):
        if kind in ('subjob.started', 'subjob.finished', 'subjob.error'):
            self._persist_work_event(job, kind, message)


class SupplementarySubjobsA14Tests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.work = root / 'Work'
        self.work.mkdir()
        self.joblist = root / 'jobs.n5jobs'
        self.joblist.write_text('placeholder', encoding='utf-8')
        self.job = Job(job_id='JOB-001', name='1525_004',
                       workflow_ids=list(HISTORIC_FLOW),
                       work_root=self.work, work_operations=self.work,
                       status=JobStatus.OK, progress=1.0,
                       next_operation_index=len(HISTORIC_FLOW))
        self.job.job_uid = '00000000-0000-4000-8000-000000000001'
        self.api = A14Api(self.job, self.work, self.joblist)

    def test_completed_legacy_job_can_plan_its_omitted_siegfried(self):
        original = tuple(self.job.workflow_ids)
        plan = extended_workflow(self.job, SIEGFRIED, self.api._registry_catalog())
        self.assertEqual(len(plan), 14)
        self.assertLess(plan.index(SIEGFRIED), plan.index('build_noark5_canonical_evidence'))
        self.assertEqual(tuple(self.job.workflow_ids), original)
        self.assertEqual(self.job.next_operation_index, 13)
        self.assertEqual(self.job.status, JobStatus.OK)

    def test_registration_does_not_reset_parent_and_is_idempotent(self):
        self.assertTrue(add_additional_subjob(self.api, 'JOB-001', SIEGFRIED))
        self.assertFalse(add_additional_subjob(self.api, 'JOB-001', SIEGFRIED))
        self.assertEqual(additional_ids(self.job), (SIEGFRIED,))
        self.assertEqual(tuple(self.job.workflow_ids), HISTORIC_FLOW)
        self.assertEqual((self.job.status, self.job.progress,
                          self.job.next_operation_index), (JobStatus.OK, 1.0, 13))
        self.assertEqual(self.api.snapshots[0][1], HISTORIC_FLOW)
        self.assertEqual(self.api.calls, ['save'])

    def test_one_added_run_logs_real_job_not_temporary_workflow(self):
        add_additional_subjob(self.api, 'JOB-001', SIEGFRIED)
        store = SimpleNamespace(run_id='20261126T000000Z-12345678',
                                append=lambda line: None,
                                finish=lambda status: self.api.calls.append(status))
        history = SimpleNamespace(begin=lambda **kwargs: store)
        with patch('app.siegfried_tool_v0111_a3.inspect_siegfried',
                   return_value=SimpleNamespace(ok=True)) as tool_check, \
             patch('app.additional_subjobs_v027_a14.RunLogStore',
                   return_value=history):
            ok = run_additional_subjob(self.api, 'JOB-001', SIEGFRIED)
        self.assertTrue(ok)
        self.assertTrue(tool_check.called)
        self.assertEqual(tuple(self.job.workflow_ids), HISTORIC_FLOW)
        self.assertEqual((self.job.status, self.job.progress,
                          self.job.next_operation_index), (JobStatus.OK, 1.0, 13))
        self.assertEqual(self.api.engine_jobs[0][1], SIEGFRIED)
        self.assertIsNot(self.api.engine_jobs[0][0], self.job)
        self.assertTrue(all(state[1] == HISTORIC_FLOW for state in self.api.snapshots))
        self.assertIn('finished', self.api.calls)
        self.assertFalse(self.api._running)

    def test_nonreentrant_api_lock_does_not_deadlock_registration(self):
        self.assertTrue(add_additional_subjob(self.api, 'JOB-001', SIEGFRIED))
        self.assertFalse(self.api._guard.locked())

    def test_existing_operation_preflight_uses_own_lock(self):
        def guarded_preflight(job_id, operation_id):
            with self.api._guard:
                return SimpleNamespace(errors=(), warnings=(), actions=())
        self.api.preflight_subjob = guarded_preflight
        result = []
        worker = Thread(target=lambda: result.append(
            inspect_additional_subjob(self.api, 'JOB-001', HISTORIC_FLOW[0])), daemon=True)
        worker.start()
        worker.join(timeout=1.5)
        self.assertFalse(worker.is_alive(), 'Non-reentrant API lock: deadlock')
        self.assertEqual(len(result), 1)

    def test_no_unapproved_operation_or_aip_package(self):
        with self.assertRaises(DwmApiError):
            run_additional_subjob(self.api, 'JOB-001', SIEGFRIED)
        with self.assertRaises(DwmApiError):
            extended_workflow(self.job, 'dias_package', self.api._registry_catalog())

    def test_required_predecessor_not_executed_refuses_supplement(self):
        self.job.workflow_ids = list(HISTORIC_FLOW[:3]) + ['run_noark5_xpath_tests_2026']
        self.job.next_operation_index = 0
        with self.assertRaises(DwmApiError):
            extended_workflow(self.job, 'build_noark5_canonical_evidence', self.api._registry_catalog())

    def test_registration_failure_rolls_back_in_memory(self):
        self.api._persist_work_event = lambda *_args: (_ for _ in ()).throw(OSError('disk'))
        with self.assertRaises(OSError):
            add_additional_subjob(self.api, 'JOB-001', SIEGFRIED)
        self.assertNotIn(EXTRA_KEY, self.job.operation_params)


if __name__ == '__main__':
    unittest.main()
