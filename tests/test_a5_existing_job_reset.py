from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A5ExistingJobResetTests(unittest.TestCase):
    def test_jobs_window_has_direct_reset_action(self):
        text = (ROOT / "gui" / "jobs_window_a22.py").read_text(encoding="utf-8")
        self.assertIn('text="Nullstill"', text)
        self.assertIn("self.reset_job_execution(job)", text)
        self.assertIn("Resultatfiler og logger på disk slettes ikke", text)

    def test_runtime_resets_cursor_without_deleting_artifacts(self):
        text = (ROOT / "gui" / "persistent_app_a37.py").read_text(encoding="utf-8")
        method = text.split("def _reset_job_execution", 1)[1].split(
            "def _open_jobs", 1
        )[0]
        self.assertIn("job.reset_execution(", method)
        self.assertIn("self._save_job_list()", method)
        self.assertNotIn("unlink(", method)
        self.assertNotIn("rmtree(", method)

    def test_a22_is_active_jobs_window_for_a5(self):
        text = (ROOT / "gui" / "persistent_app_a37.py").read_text(encoding="utf-8")
        self.assertIn("from .jobs_window_a22 import A22JobsWindow", text)
        self.assertIn("self.jobs_window = A22JobsWindow(", text)
        self.assertIn("reset_job_execution=self._reset_job_execution", text)


if __name__ == "__main__":
    unittest.main()
