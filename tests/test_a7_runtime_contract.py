from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A7RuntimeContractTests(unittest.TestCase):
    def test_main_activates_a39(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a39 import run_gui", text)

    def test_a39_uses_shared_workflow_policy(self):
        text = (
            ROOT / "gui" / "persistent_app_a39.py"
        ).read_text(encoding="utf-8")
        self.assertIn("from app.job_workflow_policy import", text)
        self.assertIn("def _workflow_preflight", text)
        self.assertIn("def _start_all_jobs", text)
        self.assertIn("def _start_ready_jobs", text)

    def test_explicit_new_job_sets_owner_when_available(self):
        text = (
            ROOT / "gui" / "persistent_app_a39.py"
        ).read_text(encoding="utf-8")
        method = text.split("def _create_job", 1)[1].split(
            "def _workflow_preflight", 1
        )[0]
        self.assertIn("current_user_identity", method)
        self.assertIn("job.set_owner_identity(identity)", method)

    def test_jobs_window_no_longer_claims_batch_is_always_sequential(self):
        text = (
            ROOT / "gui" / "jobs_window_a25.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Auto, Sekvensiell eller Parallell", text)
        self.assertIn("Scheduler:", text)


if __name__ == "__main__":
    unittest.main()
