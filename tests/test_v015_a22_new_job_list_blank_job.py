
from __future__ import annotations

import unittest
from pathlib import Path

from noark5_workflow.core.job import JobBatch


class V015A22NewJobListBlankJobTests(unittest.TestCase):
    def test_blank_job_is_job001(self):
        batch = JobBatch()
        job = batch.new_job(None)
        self.assertEqual(job.job_id, "JOB-001")
        self.assertIsNone(job.source_root)
        self.assertIsNone(job.source_extraction)
        self.assertIsNone(job.work_root)
        self.assertIsNone(job.work_operations)

    def test_a57_creates_job_only_when_list_is_empty(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "persistent_app_a57.py").read_text(encoding="utf-8")
        self.assertIn("if len(self.jobs) == 0:", text)
        self.assertIn("self.jobs.new_job(None)", text)
        self.assertIn("self.current_job = job", text)
        self.assertIn("self.workflow.clear()", text)
        self.assertIn('self.source_panel.path_var.set("")', text)

    def test_main_activates_a57_runtime(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a56 import run_gui", text)
        self.assertIn("from gui.persistent_app_a57 import run_gui", text)
        self.assertLess(
            text.index("from gui.persistent_app_a56 import run_gui"),
            text.index("from gui.persistent_app_a57 import run_gui"),
        )


if __name__ == "__main__":
    unittest.main()
