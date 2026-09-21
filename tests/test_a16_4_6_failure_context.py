from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A1646FailureContextTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (ROOT / "gui" / "persistent_app_a34.py").read_text(encoding="utf-8")

    def test_failure_summary_names_operation(self):
        self.assertIn("Stoppet på operasjon {pos}/{total}", self.runtime)
        self.assertIn("operation.definition.name", self.runtime)

    def test_failure_summary_extracts_inner_xpath_test(self):
        self.assertIn("TEST START", self.runtime)
        self.assertIn("Test: {test_context}", self.runtime)
        self.assertIn("kdrs_", self.runtime)

    def test_status_tooltip_provider_is_wired(self):
        self.assertIn(
            "self.workflow_panel.status_detail_provider = self._a1646_status_detail",
            self.runtime,
        )

    def test_failure_context_does_not_reset_execution_state(self):
        method = self.runtime.split(
            "def _runner_state_changed(self, job) -> None:", 1
        )[1].split("def _execute_job", 1)[0]
        self.assertNotIn("next_operation_index =", method)
        self.assertNotIn("job.status =", method)

    def test_current_runtime_is_a36(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a35 import WorkflowApp as _A35WorkflowApp", main)
        self.assertIn("from gui.persistent_app_a36 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
