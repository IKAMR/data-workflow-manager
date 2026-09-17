from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A8JobListSaveAsAndLogClearTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")

    def test_save_as_explicitly_makes_new_target_active(self):
        self.assertIn("self.job_list_path = target", self.runtime)
        self.assertIn("self._refresh_job_list_status()", self.runtime)
        self.assertIn("self.jobs_window.refresh()", self.runtime)

    def test_save_as_new_copy_resets_in_job_execution_history(self):
        self.assertIn("def _reset_jobs_for_new_job_list_copy", self.runtime)
        self.assertIn("job.log_entries.clear()", self.runtime)
        self.assertIn('job.reset_execution("")', self.runtime)
        self.assertIn("is_new_copy = old_path is not None and target != old_path", self.runtime)

    def test_save_as_does_not_claim_to_delete_persistent_disk_history(self):
        self.assertIn("Persistent result folders", self.runtime)
        self.assertIn("PREMIS files", self.runtime)
        self.assertIn("not deleted", self.runtime)

    def test_failed_save_as_restores_in_memory_execution_state(self):
        self.assertIn("snapshots = []", self.runtime)
        self.assertIn("job.log_entries = entries", self.runtime)
        self.assertIn("job.next_operation_index = next_index", self.runtime)

    def test_tom_button_clears_authoritative_active_job_log(self):
        self.assertIn('child.configure(command=self._clear_active_job_log)', self.runtime)
        self.assertIn("def _clear_active_job_log", self.runtime)
        self.assertIn("job.log_entries.clear()", self.runtime)
        self.assertIn("self._write_job_list(self.job_list_path)", self.runtime)


if __name__ == "__main__":
    unittest.main()
