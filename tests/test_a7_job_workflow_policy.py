import unittest
from types import SimpleNamespace

from app.job_workflow_policy import (
    has_historical_execution,
    normalise_completed_state,
    workflow_health,
)
from noark5_workflow.core.job import Job, JobStatus


class A7JobWorkflowPolicyTests(unittest.TestCase):
    def test_fresh_empty_job_is_not_historical(self):
        job = Job("JOB-001", profile_id="noark5")
        self.assertFalse(has_historical_execution(job))

    def test_completed_empty_job_is_historical(self):
        job = Job("JOB-001", profile_id="noark5")
        job.status = JobStatus.OK
        job.message = "Workflow fullført"
        self.assertTrue(has_historical_execution(job))

    def test_completed_state_normalises_cursor_and_progress(self):
        job = Job(
            "JOB-001",
            profile_id="noark5",
            workflow_ids=["one", "two"],
        )
        job.status = JobStatus.OK
        job.progress = 0.5
        job.next_operation_index = 1

        self.assertTrue(normalise_completed_state(job))
        self.assertEqual(job.next_operation_index, 2)
        self.assertEqual(job.progress, 1.0)

    def test_empty_workflow_is_not_healthy(self):
        job = Job("JOB-001", profile_id="noark5")
        self.assertFalse(workflow_health(job).ok)

    def test_duplicate_operations_are_not_healthy(self):
        job = Job(
            "JOB-001",
            profile_id="noark5",
            workflow_ids=["one", "one"],
        )
        self.assertFalse(workflow_health(job).ok)


if __name__ == "__main__":
    unittest.main()
