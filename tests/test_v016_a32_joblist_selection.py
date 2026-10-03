from __future__ import annotations

import unittest
from pathlib import Path

from gui.jobs_window import JobsWindow
from noark5_workflow.core.job import JobBatch


class A32JobListSelectionTests(unittest.TestCase):
    def test_jobs_window_tracks_selected_job_ids(self):
        batch = JobBatch()
        job_a = batch.new_job(Path("/tmp/a"), name="A")
        job_b = batch.new_job(Path("/tmp/b"), name="B")

        window = JobsWindow.__new__(JobsWindow)
        window.batch = batch
        window._selected_job_ids = {job_a.job_id}

        self.assertEqual(window._selected_job_ids_for_run(), {job_a.job_id})
        self.assertEqual(window._selected_jobs_for_run(), (job_a,))
        self.assertNotIn(job_b.job_id, window._selected_job_ids_for_run())

    def test_app_wires_selective_rerun_and_batch_runner(self):
        text = (Path(__file__).resolve().parents[1] / "gui" / "app.py").read_text(encoding="utf-8")
        self.assertIn("self.job_runner =", text)
        self.assertIn("self.workflow_panel.on_rerun = self._rerun_selected_operation", text)
        self.assertIn("_selected_jobs_for_run", text)


if __name__ == "__main__":
    unittest.main()
