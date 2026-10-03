from __future__ import annotations

import time
import unittest
from pathlib import Path

from gui.app import WorkflowApp
from noark5_workflow.core.job import Job, JobBatch, JobStatus


class V016A33Step14Tests(unittest.TestCase):
    def test_bulk_assign_default_noark5_workflow_sets_empty_jobs(self):
        app = WorkflowApp.__new__(WorkflowApp)
        app.settings = {"noark5_discovery_workflow": "noark5_standard"}
        app.jobs = JobBatch()
        app._job_position = lambda job: 1
        app._get_app_work_subfolder = lambda: "dwm"

        empty = app.jobs.new_job(Path("/tmp/empty"), name="empty")
        empty.profile_id = "noark5"
        filled = app.jobs.new_job(Path("/tmp/filled"), name="filled")
        filled.profile_id = "noark5"
        filled.set_workflow(["metadata_overview"])

        assigned = app._bulk_assign_default_noark5_workflow(app.jobs.jobs())

        self.assertEqual([job.job_id for job in assigned], [empty.job_id])
        self.assertTrue(empty.workflow_ids)
        self.assertTrue(filled.workflow_ids)
        self.assertEqual(empty.profile_id, "noark5")
        self.assertEqual(filled.profile_id, "noark5")

        all_assigned = app._bulk_assign_default_noark5_workflow(app.jobs.jobs(), include_empty_only=False)
        self.assertEqual([job.job_id for job in all_assigned], [empty.job_id, filled.job_id])

    def test_eligible_batch_jobs_skips_done_jobs_and_recovers_interrupted_jobs(self):
        app = WorkflowApp.__new__(WorkflowApp)
        batch = JobBatch()
        done = batch.new_job(Path("/tmp/done"), name="done")
        done.status = JobStatus.OK
        running = batch.new_job(Path("/tmp/running"), name="running")
        running.status = JobStatus.RUNNING
        waiting = batch.new_job(Path("/tmp/waiting"), name="waiting")
        waiting.status = JobStatus.WAITING
        failed_retry = batch.new_job(Path("/tmp/failed"), name="failed")
        failed_retry.set_workflow(["metadata_overview"])
        failed_retry.status = JobStatus.FAILED
        failed_retry.message = "Workflow stoppet med feil"
        empty_failed = batch.new_job(Path("/tmp/empty-failed"), name="empty-failed")
        empty_failed.status = JobStatus.FAILED

        eligible = app._eligible_batch_jobs(batch.jobs())
        ids = [job.job_id for job in eligible]

        self.assertIn(running.job_id, ids)
        self.assertIn(waiting.job_id, ids)
        self.assertIn(failed_retry.job_id, ids)
        self.assertNotIn(done.job_id, ids)
        self.assertNotIn(empty_failed.job_id, ids)
        self.assertEqual(running.status, JobStatus.WAITING)

    def test_start_selected_jobs_reuses_selected_subset_only(self):
        app = WorkflowApp.__new__(WorkflowApp)
        app.batch_running = False
        app.batch_cancel_requested = False
        app.current_job = None
        app.jobs_window = None
        app.after = lambda *args, **kwargs: None
        app._open_job = lambda *args, **kwargs: None
        app._execute_job = lambda *args, **kwargs: None
        app.workflow_panel = type("WorkflowPanelStub", (), {"run_button": type("RunButton", (), {"configure": lambda self, **kwargs: None})()})()
        app.log_panel = type("LogPanelStub", (), {"append": lambda self, *_args, **_kwargs: None})()
        app.status_bar = type("StatusBarStub", (), {"set_status": lambda self, *_args, **_kwargs: None})()

        batch = JobBatch()
        selected = batch.new_job(Path("/tmp/one"), name="one")
        skipped = batch.new_job(Path("/tmp/two"), name="two")
        selected.status = JobStatus.READY
        skipped.status = JobStatus.OK

        app.jobs = batch
        app.jobs_window = type("WindowStub", (), {
            "winfo_exists": lambda self: True,
            "_selected_jobs_for_run": lambda self: (selected,),
            "set_batch_running": lambda self, *_: None,
            "schedule_refresh": lambda self: None,
        })()

        app._start_batch_jobs((selected, skipped))
        deadline = time.monotonic() + 1.0
        while app.batch_running and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(app.batch_running)


if __name__ == "__main__":
    unittest.main()
