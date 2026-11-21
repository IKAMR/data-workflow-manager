"""v0.2.4-a2: real core run() resumes READY at failed operation.

The test is skipped only in a standalone delta tree without the repository.
When installed into DWM it exercises the existing core JobRunner directly.
"""
from __future__ import annotations

import unittest
from pathlib import Path

try:
    from noark5_workflow.core.job import Job, JobStatus
    from noark5_workflow.core.job_runner import JobRunner
    from tests.test_job_runner_a4 import FakeRegistry, FakeExecutor, FakeOperation
    HAVE_CORE = True
except ImportError:
    HAVE_CORE = False


@unittest.skipUnless(HAVE_CORE, 'Krever kjernemodulene i DWM-repoet')
class RealRunnerContinue(unittest.TestCase):
    def test_ready_partial_cursor_keeps_completed_prefix(self):
        a = FakeOperation('first')
        b = FakeOperation('second')
        c = FakeOperation('third', ok=False)
        runner = JobRunner(FakeRegistry((a, b, c)), FakeExecutor(), {},
                           source_factory=lambda _path: object())
        job = Job('JOB-001', Path('source'), workflow_ids=['first','second','third'])
        failed = runner.run(job)
        self.assertFalse(failed.ok)
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertEqual(job.next_operation_index, 2)
        self.assertEqual((a.calls, b.calls, c.calls), (1, 1, 1))
        # a2 API records the Work event and makes a deliberate FAILED -> READY
        # transition, retaining the authoritative cursor.
        job.status = JobStatus.READY
        job.message = 'Fortsettelse fra deljobb 3 av 3'
        c.ok = True
        completed = runner.run(job)
        self.assertTrue(completed.ok)
        self.assertEqual(job.status, JobStatus.OK)
        self.assertEqual(job.next_operation_index, 3)
        self.assertEqual((a.calls, b.calls, c.calls), (1, 1, 2))


if __name__ == '__main__':
    unittest.main()
