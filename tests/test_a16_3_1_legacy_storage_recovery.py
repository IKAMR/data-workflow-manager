from __future__ import annotations

import unittest

from noark5_workflow.core.job import Job, JobStatus
from gui.jobs_window_a19 import A19JobsWindow
from gui.persistent_app_a30 import WorkflowApp


class A1631LegacyStorageRecoveryTests(unittest.TestCase):
    def _legacy_failed_job(self):
        job = Job(
            "JOB-004",
            workflow_ids=["op1", "op2", "op3", "xpath", "views", "report"],
            status=JobStatus.FAILED,
            message=(
                "[Errno 22] Invalid argument: "
                "G:\\arkiv-noark5\\1543\\repository_operations\\result.json"
            ),
        )
        job.next_operation_index = 3
        job.operation_params = {
            "xpath": {"profile": "normal"},
        }
        return job

    def test_old_errno_22_failure_is_recoverable_without_prefix(self):
        job = self._legacy_failed_job()
        self.assertTrue(WorkflowApp._recoverable_storage_failure(job))
        self.assertTrue(A19JobsWindow._is_ready_to_run(job))

    def test_migration_keeps_cursor_and_parameters(self):
        app = object.__new__(WorkflowApp)
        app._job_log = lambda *args, **kwargs: None
        job = self._legacy_failed_job()

        old_index = job.next_operation_index
        old_params = dict(job.operation_params)

        changed = app._mark_legacy_storage_failure_recoverable(job)

        self.assertTrue(changed)
        self.assertEqual(old_index, job.next_operation_index)
        self.assertEqual(old_params, job.operation_params)
        self.assertEqual(JobStatus.FAILED, job.status)
        self.assertTrue(
            job.message.startswith("Lagring utilgjengelig - kan fortsette:")
        )

    def test_non_io_failure_is_not_migrated(self):
        app = object.__new__(WorkflowApp)
        app._job_log = lambda *args, **kwargs: None
        job = Job(
            "JOB-001",
            workflow_ids=["one"],
            status=JobStatus.FAILED,
            message="Faglig valideringsfeil",
        )

        self.assertFalse(app._mark_legacy_storage_failure_recoverable(job))
        self.assertEqual("Faglig valideringsfeil", job.message)

    def test_job_window_labels_legacy_failure_as_can_continue(self):
        job = self._legacy_failed_job()
        window = object.__new__(A19JobsWindow)
        self.assertEqual("Feil - kan fortsette", window._status_text(job))


if __name__ == "__main__":
    unittest.main()
