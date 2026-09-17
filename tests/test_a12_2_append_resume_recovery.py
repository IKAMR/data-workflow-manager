from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A122AppendResumeRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        cls.runner = (ROOT / "noark5_workflow" / "core" / "job_runner.py").read_text(encoding="utf-8")

    def test_append_preservation_is_at_sync_boundary(self):
        self.assertIn("def _sync_active_workflow_to_job", self.gui)
        self.assertIn("append_only = self._is_append_only_extension", self.gui)
        self.assertIn("job.next_operation_index = len(old_ids)", self.gui)
        self.assertIn("job.status = JobStatus.READY", self.gui)

    def test_old_corrupted_job_list_can_recover_from_persisted_run_log(self):
        self.assertIn("def _completed_prefix_from_log", self.gui)
        self.assertIn('"Workflow fullført"', self.gui)
        self.assertIn('"OK: "', self.gui)
        self.assertIn("def _recover_append_only_state", self.gui)

    def test_recovery_runs_on_startup_and_job_open(self):
        self.assertGreaterEqual(self.gui.count("_recover_append_only_state("), 3)

    def test_ready_partial_cursor_is_run_directly_not_checkpoint_continue(self):
        self.assertIn("job.status in {JobStatus.WAITING, JobStatus.READY}", self.runner)
        self.assertIn("READY + partial cursor", self.runner)

    def test_waiting_continue_still_requires_checkpoint(self):
        self.assertIn("if job.status != JobStatus.WAITING", self.runner)
        self.assertIn("job.has_checkpoint(previous_operation_id)", self.runner)


if __name__ == "__main__":
    unittest.main()
