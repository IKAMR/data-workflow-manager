from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A154CleanJobListDiscoveryTests(unittest.TestCase):
    def test_top_runtime_uses_single_draft_new_list_fix(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        runtime = (ROOT / "gui" / "persistent_app_a23.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a23 import run_gui", main)
        self.assertIn("A17WorkflowApp._new_job_list(self)", runtime)
        self.assertEqual(runtime.count("job = self._create_job(None)"), 1)

    def test_discovery_collapses_old_all_blank_state(self):
        text = (ROOT / "gui" / "jobs_window_a17.py").read_text(encoding="utf-8")
        self.assertIn("all(job.is_unused_draft() for job in jobs)", text)
        self.assertIn("self.batch.remove(extra.job_id)", text)

    def test_reused_first_job_gets_all_storage_roles(self):
        text = (ROOT / "gui" / "jobs_window_a17.py").read_text(encoding="utf-8")
        marker = "if index == 0 and reusable_draft is not None:"
        block = text.split(marker, 1)[1].split("else:", 1)[0]
        self.assertIn("self._apply_roles(job, roles)", block)
        self.assertIn("job.name = name", block)


if __name__ == "__main__":
    unittest.main()
