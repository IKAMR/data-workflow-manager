"""a15 regression: dependent Work repairs do not reset historical jobs."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from app.additional_subjobs_v027_a14 import EXTRA_KEY, SIEGFRIED
from app.aftercare_v027_a15 import (
    STATE_KEY, affected_operations, aftercare_plan, aftercare_summary,
    execute_aftercare, read_aftercare,
)
from app.application_api import DwmApiError
from noark5_workflow.core.job import Job, JobStatus

HISTORIC = (
    'metadata_inventory', 'validate_xml_schema', 'analyse_arkivstruktur',
    'arkade5_noark5_test', 'arkade5_pronom_analysis',
    'run_noark5_xpath_tests_2026', 'import_arkade5_reports',
    'build_noark5_canonical_evidence', 'analyze_noark5_external_evidence',
    'audit_noark5_evidence', 'compose_noark5_views',
    'build_noark5_depot_report', 'build_noark5_qa_draft',
)
DOWNSTREAM = (
    'build_noark5_canonical_evidence', 'analyze_noark5_external_evidence',
    'audit_noark5_evidence', 'compose_noark5_views',
    'build_noark5_depot_report', 'build_noark5_qa_draft',
)


class FakeApi:
    def __init__(self, work: Path):
        self.job = Job(job_id='JOB-001', name='1525_004',
                       workflow_ids=list(HISTORIC),
                       status=JobStatus.OK, progress=1.0,
                       next_operation_index=len(HISTORIC))
        self.job.set_operation_params(EXTRA_KEY, {'operation_ids': [SIEGFRIED]})
        self.job.job_uid = '00000000-0000-4000-8000-000000000001'
        self.work = work
        self._guard = Lock()
        self._running = False
        self._work_references = {'JOB-001': work / 'job.json'}
        self._unavailable_work_ids = set()
        self.settings = {'sf_executable': 'sf.exe'}
        self._dirty = False
        self.calls = []
        self.work_snapshots = []
        self.fail_operation = None
        self.have_new_run = False

    def _assert_idle(self):
        if self._running:
            raise DwmApiError('Kjoring pagar')

    def _require_job(self, job_id):
        if job_id != self.job.job_id:
            raise DwmApiError('Ukjent jobb')
        return self.job

    def workspace(self):
        return SimpleNamespace(job_list_path=str(self.work.parent / 'saved.n5jobs'),
            jobs=(SimpleNamespace(job_id='JOB-001',
                effective_work_operations=str(self.work)),))

    def _persist_work_event(self, job, kind, detail):
        self.work_snapshots.append((kind, tuple(job.workflow_ids),
            job.status, job.progress, job.next_operation_index,
            tuple(read_aftercare(job).get('pending', ()))) )

    def save_job_list(self):
        self.calls.append('save')
        return self.work.parent / 'saved.n5jobs'

    def run_subjob(self, job_id, operation_id, **kwargs):
        self.calls.append(operation_id)
        return operation_id != self.fail_operation


class A15AftercareTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name) / 'Work'
        self.work.mkdir()
        self.api = FakeApi(self.work)
        self.a14_calls = []
        self.link_calls = []
        self.preflight_calls = []
        self.patches = (
            patch('app.aftercare_v027_a15._preflight', side_effect=self._preflight),
            patch('app.aftercare_v027_a15._runs', side_effect=self._runs),
            patch('app.aftercare_v027_a15.run_additional_subjob', side_effect=self._extra),
            patch('app.aftercare_v027_a15.verify_siegfried_link', side_effect=self._linked),
            patch('app.aftercare_v027_a15.reconcile_supplemental_audit', return_value=True),
        )
        for mocked in self.patches:
            mocked.start()
            self.addCleanup(mocked.stop)

    def _preflight(self, api, job_id, operation, approved):
        self.preflight_calls.append(operation)

    def _runs(self, work, job_id, operation):
        if operation == SIEGFRIED and self.api.have_new_run:
            return {'20261126T100000Z-12345678': 'finished'}
        return {}

    def _extra(self, api, job_id, operation, **kwargs):
        self.a14_calls.append(operation)
        self.api.have_new_run = True
        return True

    def _linked(self, work, run_id):
        self.link_calls.append(run_id)
        return {'run_id': run_id}

    def test_graph_follows_all_siegfried_evidence_and_reports(self):
        self.assertEqual(affected_operations(SIEGFRIED), DOWNSTREAM)
        self.assertIn('import_arkade5_reports', affected_operations('arkade5_pronom_analysis'))
        self.assertNotIn('arkade5_noark5_test', affected_operations(SIEGFRIED))
        self.assertNotIn('validate_xml_schema', affected_operations(SIEGFRIED))

    def test_completed_thirteen_step_job_has_six_dependent_repairs(self):
        plan = aftercare_plan(self.api.job, SIEGFRIED)
        self.assertEqual(plan.downstream, DOWNSTREAM)
        self.assertEqual(plan.not_configured, ())
        self.assertEqual(plan.deferred, ())

    def test_unexecuted_downstream_is_not_falsely_marked_completed(self):
        self.api.job.next_operation_index = 7
        plan = aftercare_plan(self.api.job, SIEGFRIED)
        self.assertEqual(plan.downstream, ())
        self.assertEqual(plan.deferred, DOWNSTREAM)

    def test_completed_cascade_preserves_parent_and_refreshes_six_steps(self):
        self.assertTrue(execute_aftercare(self.api, 'JOB-001', SIEGFRIED))
        self.assertEqual(self.a14_calls, [SIEGFRIED])
        self.assertEqual([v for v in self.api.calls if v in DOWNSTREAM], list(DOWNSTREAM))
        self.assertEqual(self.link_calls, ['20261126T100000Z-12345678'])
        self.assertEqual(read_aftercare(self.api.job)['status'], 'current')
        self.assertEqual(read_aftercare(self.api.job)['pending'], [])
        self.assertEqual(read_aftercare(self.api.job)['done'], list(DOWNSTREAM))
        self.assertEqual((self.api.job.status, self.api.job.progress,
                          self.api.job.next_operation_index), (JobStatus.OK, 1.0, 13))
        self.assertEqual(tuple(self.api.job.workflow_ids), HISTORIC)
        self.assertTrue(all(x[1] == HISTORIC and x[2] == JobStatus.OK
                            for x in self.api.work_snapshots))
        self.assertIn('oppdatert', aftercare_summary(self.api.job))

    def test_failure_preserves_pending_without_running_later_reports(self):
        self.api.fail_operation = DOWNSTREAM[1]
        self.assertFalse(execute_aftercare(self.api, 'JOB-001', SIEGFRIED))
        state = read_aftercare(self.api.job)
        self.assertEqual(state['status'], 'blocked')
        self.assertEqual(state['done'], [DOWNSTREAM[0]])
        self.assertEqual(state['pending'], list(DOWNSTREAM[1:]))
        self.assertNotIn(DOWNSTREAM[-1], self.api.calls)
        self.assertEqual(self.api.job.next_operation_index, 13)
        self.assertIn('utdaterte', aftercare_summary(self.api.job))

    def test_resume_starts_with_failed_derived_operation_no_new_siegfried(self):
        self.api.fail_operation = DOWNSTREAM[1]
        self.assertFalse(execute_aftercare(self.api, 'JOB-001', SIEGFRIED))
        self.api.fail_operation = None
        self.api.calls.clear()
        self.assertTrue(execute_aftercare(self.api, 'JOB-001', SIEGFRIED, resume=True))
        self.assertEqual(self.a14_calls, [SIEGFRIED])
        self.assertEqual([v for v in self.api.calls if v in DOWNSTREAM],
                         list(DOWNSTREAM[1:]))
        self.assertEqual(read_aftercare(self.api.job)['status'], 'current')

    def test_operator_can_defer_derived_processing_and_resume(self):
        self.assertTrue(execute_aftercare(self.api, 'JOB-001', SIEGFRIED,
                                          update_dependents=False))
        state = read_aftercare(self.api.job)
        self.assertEqual(state['status'], 'pending')
        self.assertEqual(state['pending'], list(DOWNSTREAM))
        self.assertTrue(execute_aftercare(self.api, 'JOB-001', SIEGFRIED, resume=True))
        self.assertEqual(self.a14_calls, [SIEGFRIED])

    def test_cancel_between_steps_stops_only_aftercare(self):
        callback_calls = []
        def cancelled():
            callback_calls.append('stop-check')
            return bool(self.a14_calls) and bool(self.api.calls.count(DOWNSTREAM[0]))
        self.assertFalse(execute_aftercare(self.api, 'JOB-001', SIEGFRIED,
                                           cancelled=cancelled))
        self.assertEqual(read_aftercare(self.api.job)['status'], 'blocked')
        self.assertEqual(read_aftercare(self.api.job)['pending'], list(DOWNSTREAM[1:]))
        self.assertEqual(self.api.job.status, JobStatus.OK)

    def test_persistence_happens_outside_nonreentrant_lock(self):
        original_save = self.api.save_job_list
        def check_save():
            self.assertFalse(self.api._guard.locked())
            return original_save()
        self.api.save_job_list = check_save
        self.assertTrue(execute_aftercare(self.api, 'JOB-001', SIEGFRIED))

    def test_unregistered_supplement_is_rejected_without_mutation(self):
        self.api.job.operation_params.pop(EXTRA_KEY, None)
        with self.assertRaises(DwmApiError):
            aftercare_plan(self.api.job, SIEGFRIED)
        self.assertNotIn(STATE_KEY, self.api.job.operation_params)


if __name__ == '__main__':
    unittest.main()
