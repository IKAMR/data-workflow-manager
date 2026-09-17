from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A124RetryFailedAppendResumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        cls.runner = (ROOT / "noark5_workflow" / "core" / "job_runner.py").read_text(encoding="utf-8")

    def test_failed_append_resume_is_recovered_from_persisted_log(self):
        self.assertIn("def _recover_failed_append_retry_state", self.gui)
        self.assertIn("Workflow fortsetter fra operasjon", self.gui)
        self.assertIn("Fortsettelse feilet - prøv igjen fra operasjon", self.gui)

    def test_failed_partial_cursor_gets_retry_button(self):
        self.assertIn('self.workflow_panel.set_run_text("Prøv igjen")', self.gui)
        self.assertIn("job.status == JobStatus.FAILED", self.gui)

    def test_runner_accepts_only_explicit_retryable_failed_cursor(self):
        self.assertIn("failed_retry = (", self.runner)
        self.assertIn('startswith("Fortsettelse feilet - prøv igjen fra operasjon ")', self.runner)
        self.assertIn("and not failed_retry", self.runner)

    def test_resumed_exception_keeps_failed_operation_cursor_retryable(self):
        self.assertGreaterEqual(
            self.runner.count("Fortsettelse feilet - prøv igjen fra operasjon"),
            3,
        )
        self.assertIn("if resuming else str(exc)", self.runner)

    def test_checkpoint_semantics_remain_separate(self):
        self.assertIn("if job.status != JobStatus.WAITING", self.runner)
        self.assertIn("job.has_checkpoint(previous_operation_id)", self.runner)


if __name__ == "__main__":
    unittest.main()
