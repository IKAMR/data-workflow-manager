from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A10ActiveJobRestoreTests(unittest.TestCase):

    def test_active_job_is_persisted_when_opened(self):
        source = (ROOT / "gui" / "persistent_app_a70.py").read_text(
            encoding="utf-8"
        )
        block = source.split("def _open_job(self, job)", 1)[1].split(
            "def _open_validation_overview", 1
        )[0]
        self.assertIn("super()._open_job(job)", block)
        self.assertIn("self._write_job_list(self.job_list_path)", block)

    def test_depot_assessment_still_uses_current_job_work_operations(self):
        source = (ROOT / "gui" / "persistent_app_a70.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("job = self.current_job", source)
        self.assertIn('getattr(job, "_effective_work_operations", None)', source)
        self.assertIn('getattr(job, "work_operations", None)', source)


if __name__ == "__main__":
    unittest.main()
