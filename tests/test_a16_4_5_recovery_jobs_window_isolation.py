from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A1645RecoveryJobsWindowIsolationTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (ROOT / "gui" / "persistent_app_a33.py").read_text(encoding="utf-8")

    def test_jobs_window_is_detached_during_recovery_executor(self):
        method = self.runtime.split(
            "def _execute_job(self, job, *, batch_mode: bool) -> bool:", 1
        )[1].split("def run_gui", 1)[0]
        save_pos = method.index("saved_jobs_window = self.jobs_window")
        detach_pos = method.index("self.jobs_window = None")
        execute_pos = method.index("A28WorkflowApp._execute_job(")
        restore_pos = method.index("self.jobs_window = saved_jobs_window")
        self.assertLess(save_pos, detach_pos)
        self.assertLess(detach_pos, execute_pos)
        self.assertLess(execute_pos, restore_pos)

    def test_no_jobs_window_refresh_between_waiting_and_executor(self):
        method = self.runtime.split(
            "def _execute_job(self, job, *, batch_mode: bool) -> bool:", 1
        )[1].split("def run_gui", 1)[0]
        waiting_pos = method.index("job.status = JobStatus.WAITING")
        execute_pos = method.index("A28WorkflowApp._execute_job(")
        between = method[waiting_pos:execute_pos]
        self.assertNotIn("refresh()", between)
        self.assertNotIn("messagebox", between)

    def test_cursor_and_params_still_preserved(self):
        self.assertIn("cursor = int(job.next_operation_index or 0)", self.runtime)
        self.assertIn("params_before = dict(job.operation_params or {})", self.runtime)
        self.assertIn("job.operation_params = params_before", self.runtime)

    def test_current_runtime_is_a36(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a35 import WorkflowApp as _A35WorkflowApp", main)
        self.assertIn("from gui.persistent_app_a36 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
