from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A5ExistingJobResetFix2Tests(unittest.TestCase):
    def test_reset_reloads_active_job_with_existing_runtime_method(self):
        text = (ROOT / "gui" / "persistent_app_a37.py").read_text(encoding="utf-8")
        method = text.split(
            "def _reset_job_execution", 1
        )[1].split("def _open_jobs", 1)[0]
        self.assertIn("self._open_job(job)", method)
        self.assertNotIn("_load_job_into_view", method)


if __name__ == "__main__":
    unittest.main()
