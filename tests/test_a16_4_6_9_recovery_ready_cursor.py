from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A16469RecoveryReadyCursorTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (
            ROOT / "gui" / "persistent_app_a36.py"
        ).read_text(encoding="utf-8")

    def test_recovery_uses_ready_not_waiting_before_executor(self):
        method = self.runtime.split(
            "def _execute_job(self, job, *, batch_mode: bool) -> bool:", 1
        )[1].split("def _confirm_rerun", 1)[0]

        ready_pos = method.index("job.status = JobStatus.READY")
        execute_pos = method.index("A28WorkflowApp._execute_job(")

        self.assertLess(ready_pos, execute_pos)
        self.assertNotIn("job.status = JobStatus.WAITING", method)

    def test_recovery_keeps_failed_operation_cursor_and_params(self):
        method = self.runtime.split(
            "def _execute_job(self, job, *, batch_mode: bool) -> bool:", 1
        )[1].split("def _confirm_rerun", 1)[0]

        self.assertIn("cursor = int(job.next_operation_index or 0)", method)
        self.assertIn("params_before = dict(job.operation_params or {})", method)
        self.assertIn("job.operation_params = params_before", method)
        self.assertNotIn("next_operation_index =", method)

    def test_recovery_bypasses_checkpoint_continue_route(self):
        method = self.runtime.split(
            "def _execute_job(self, job, *, batch_mode: bool) -> bool:", 1
        )[1].split("def _confirm_rerun", 1)[0]

        self.assertIn("A28WorkflowApp._execute_job(", method)
        self.assertNotIn("continue_job", method)

    def test_current_runtime_remains_a36(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn(
            "from gui.persistent_app_a35 import WorkflowApp as _A35WorkflowApp",
            main,
        )
        self.assertIn("from gui.persistent_app_a36 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
