from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A1644ImmediateResumeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (
            ROOT / "gui" / "persistent_app_a32.py"
        ).read_text(encoding="utf-8")

    def test_recovery_enters_executor_immediately_after_waiting_handoff(self):
        method = self.runtime.split(
            "def _execute_job(self, job, *, batch_mode: bool) -> bool:", 1
        )[1].split("def run_gui", 1)[0]

        waiting_pos = method.index("job.status = JobStatus.WAITING")
        execute_pos = method.index("A28WorkflowApp._execute_job(")

        between = method[waiting_pos:execute_pos]
        self.assertNotIn("_write_job_list", between)
        self.assertNotIn("self.after(", between)
        self.assertNotIn("jobs_window.refresh", between)

    def test_cursor_and_params_are_preserved(self):
        self.assertIn(
            "cursor = int(job.next_operation_index or 0)",
            self.runtime,
        )
        self.assertIn(
            "params_before = dict(job.operation_params or {})",
            self.runtime,
        )
        self.assertIn(
            "job.operation_params = params_before",
            self.runtime,
        )

    def test_a32_is_preserved_and_current_runtime_is_a34(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn(
            "from gui.persistent_app_a32 import WorkflowApp as _A32WorkflowApp",
            main,
        )
        self.assertIn(
            "from gui.persistent_app_a33 import WorkflowApp as _A33WorkflowApp",
            main,
        )
        self.assertIn(
            "from gui.persistent_app_a34 import run_gui",
            main,
        )


if __name__ == "__main__":
    unittest.main()
