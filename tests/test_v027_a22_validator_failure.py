"""A22: external failure is not success, and partial QA never implies approval."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

from app import validator_failure_v027_a22 as policy
from app.batch_continue_v025_a3 import batch_can_advance, plan_remaining_jobs
from app.basic_run_feedback_v0111_a3 import planned_operation_rows
from app.run_progress_v018_a8 import saved_progress
from noark5_workflow.core.job import Job, JobStatus
from noark5_workflow.core.job_runner import JobRunner
from noark5_workflow.core.result import OperationResult
from noark5_workflow.core.preflight import JobPreflight


class ValidatorA22Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.ids = ['metadata_inventory', 'validate_xml_schema', 'analyse_arkivstruktur',
                    'run_noark5_xpath_tests_2026', policy.A150,
                    'siegfried_pronom_identification', *policy.PIPELINE]
        self.job = Job('JOB-001', source_root=self.root, work_operations=self.root,
                       workflow_ids=self.ids, next_operation_index=4, progress=4/14)
        self.job.job_uid = '00000000-0000-4000-8000-000000000001'
        (self.root/'job.json').write_text(json.dumps({
            'file_type': 'dwm-work-job', 'job_uid': self.job.job_uid,
            'job': {'job_id': self.job.job_id, 'workflow_ids': self.ids}}), encoding='utf-8')
        self.calls = []
        self.logs = []
        self.results = {
            policy.A150: OperationResult(False, 'Arkade 5 feilet teknisk', data={
                'a22_validator_failure': {'kind': 'source_access_denied', 'cli_run_id': 'cli-1',
                                          'paths': [r'G:\source\DOKUMENT\file.pdf'], 'exit_code': 0},
                '_result_ref': {'result_id': 'result-1', 'job_uid': self.job.job_uid,
                                'run_id': 'workflow-1'}}),
            policy.A230: OperationResult(True, 'Mangler Arkade Noark 5', data={
                'status': 'missing_expected_sources', 'missing': ['arkade_noark'],
                'evidence_complete': False}),
        }
        self.runner = JobRunner(
            NS(get=lambda op: NS(definition=NS(operation_id=op, name=op))),
            NS(execute=self.execute), {}, source_factory=lambda path: None)

    def execute(self, operation, ctx):
        op = operation.definition.operation_id
        self.calls.append(op)
        if op == policy.A200:
            self.assertIn(policy.A150, ctx.metadata['a22_deferred_validators'])
        return self.results.get(op, OperationResult(True, 'OK'))

    def run_job(self, **kwargs):
        return self.runner.run(self.job, log_cb=self.logs.append, **kwargs)

    def test_resume_a150_and_complete_with_deviation(self):
        self.assertTrue(self.run_job().ok)
        self.assertEqual(self.calls, self.ids[4:])
        self.assertEqual(self.job.status, JobStatus.PARTIAL)
        self.assertEqual(self.job.progress, 1)
        self.assertEqual(self.job.next_operation_index, 14)
        self.assertEqual(policy.failures(self.job)[policy.A150]['raw_result_id'], 'result-1')
        self.assertIn('FEIL: ' + policy.A150, self.logs)
        self.assertTrue(batch_can_advance(True, self.job.status.value))
        self.assertEqual(JobPreflight().find_reruns([self.job]), [self.job])

    def test_unclassified_error_stops(self):
        self.results[policy.A150] = OperationResult(False, 'Launch error')
        self.assertFalse(self.run_job().ok)
        self.assertEqual(self.calls, [policy.A150])
        self.assertEqual(self.job.status, JobStatus.FAILED)
        self.assertEqual(self.job.next_operation_index, 4)
        self.assertFalse(policy.failures(self.job))

    def test_missing_audit_blocks(self):
        self.results[policy.A230] = OperationResult(True, 'Wrong sources', data={
            'status': 'sources_linked_needs_review', 'missing': []})
        self.assertFalse(self.run_job().ok)
        self.assertEqual(self.calls[-1], policy.A230)
        self.assertEqual(self.job.next_operation_index, self.ids.index(policy.A230))
        self.assertEqual(self.job.status, JobStatus.FAILED)

    def test_a160_error_preserves_a150_then_resumes(self):
        self.results[policy.A160] = OperationResult(False, 'PRONOM failed')
        self.assertFalse(self.run_job().ok)
        self.assertIn(policy.A150, policy.failures(self.job))
        self.assertEqual(self.job.next_operation_index, self.ids.index(policy.A160))
        self.results.pop(policy.A160)
        self.calls.clear()
        self.assertTrue(self.run_job().ok)
        self.assertEqual(self.calls[0], policy.A160)
        self.assertNotIn(policy.A150, self.calls)
        self.assertEqual(self.job.status, JobStatus.PARTIAL)

    def test_historical_arkade_import_stops_for_selection(self):
        p = self.root/'external_evidence'/'arkade5'/'old'/'manifest.json'
        p.parent.mkdir(parents=True)
        p.write_text('{}', encoding='utf-8')
        self.assertFalse(self.run_job().ok)
        self.assertEqual(self.calls, [policy.A150])

    def test_foreign_raw_reference_stops(self):
        self.results[policy.A150].data['_result_ref']['job_uid'] = 'other'
        self.assertFalse(self.run_job().ok)
        self.assertEqual(self.calls, [policy.A150])

    def test_missing_dependency_stops(self):
        self.job.workflow_ids.remove(policy.A230)
        self.assertFalse(self.run_job().ok)
        self.assertEqual(self.calls, [policy.A150])

    def test_checkpoint_stops_on_a150(self):
        self.job.set_checkpoint(policy.A150, True)
        self.assertFalse(self.run_job().ok)
        self.assertEqual(self.calls, [policy.A150])

    def test_cancellation_does_not_defer(self):
        self.assertFalse(self.run_job(cancelled_cb=lambda: bool(self.calls)).ok)
        self.assertEqual(self.job.status, JobStatus.INTERRUPTED)
        self.assertEqual(self.job.next_operation_index, 4)
        self.assertFalse(policy.failures(self.job))

    def test_reset_clears_active_deviation(self):
        self.assertTrue(self.run_job().ok)
        self.job.reset_execution()
        self.assertFalse(policy.failures(self.job))
        self.assertEqual(self.job.status, JobStatus.READY)

    def test_batch_excludes_partial_and_advances(self):
        view = NS(job_id='JOB-001', name='Partial', status='Fullf\u00f8rt med avvik',
                  progress=1, current_operation=14, operation_count=14)
        fresh = NS(job_id='JOB-003', name='New', status='Klar',
                   progress=0, current_operation=0, operation_count=14)
        plan = plan_remaining_jobs([view, fresh], details_for=lambda _: NS(message=''),
                                   resume_for=lambda _: None)
        self.assertEqual(plan.completed, ('JOB-001',))
        self.assertEqual(plan.targets, [('JOB-003', False, False)])
        self.assertFalse(batch_can_advance(False, view.status))
        self.assertFalse(batch_can_advance(True, 'Feil'))

    def test_views_show_error_not_completed(self):
        op = NS(operation_id=policy.A150, position=1, name='Arkade Noark',
                completed=False, failure_message='Access denied')
        self.assertEqual(planned_operation_rows([op], 'Fullf\u00f8rt med avvik', 1)[0][2], 'Teknisk feil')
        details = NS(job=NS(operation_count=1, current_operation=1, progress=1,
                           status='Fullf\u00f8rt med avvik', job_id='JOB-001', name='Partial'),
                     operations=[op], message='Partial')
        line = saved_progress(details).lines[0]
        self.assertIn('Access denied', line)
        self.assertNotIn('OK (lagret)', line)

    def test_output_freshness(self):
        before = policy.file_snapshot(self.root)
        (self.root/'filformatinfo').write_text('inventory', encoding='utf-8')
        self.assertFalse(policy.fresh_output(before, policy.file_snapshot(self.root)))
        (self.root/'filformatinfo-statistikk.csv').write_text('stats', encoding='utf-8')
        after = policy.file_snapshot(self.root)
        self.assertTrue(policy.fresh_output(before, after))
        self.assertFalse(policy.fresh_output(after, after))


class CliAccessErrorTests(unittest.TestCase):
    def make_run(self, text):
        return NS(ok=False, plan=NS(run_id='cli-1'), generated_reports=(),
                  result=NS(ok=True, exit_code=0, cancelled=False, timed_out=False,
                            launch_error='', stdout=text, stderr=''))

    def test_exact_observed_error(self):
        run = self.make_run("[Error] Access to the path 'G:\\source\\DOKUMENT\\file.pdf' is denied.\n"
                            "[Warning] Arkade 5 CLI 2.13.1 {test} finished with errors.")
        self.assertEqual(policy.access_failure(run, r'G:\source')['kind'], 'source_access_denied')
        self.assertIsNone(policy.access_failure(run, r'G:\different'))
        run.result.cancelled = True
        self.assertIsNone(policy.access_failure(run, r'G:\source'))

    def test_mixed_errors_not_deferred(self):
        run = self.make_run("[Error] Access to the path 'G:\\source\\file.pdf' is denied.\n"
                            "[Error] XML parse error\n[Warning] finished with errors")
        self.assertIsNone(policy.access_failure(run, r'G:\source'))


if __name__ == '__main__':
    unittest.main()
