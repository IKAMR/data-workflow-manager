from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A5WorkflowAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (
            ROOT / "gui" / "persistent_app_a37.py"
        ).read_text(encoding="utf-8")

    def test_stale_empty_gui_workflow_does_not_erase_job_workflow(self):
        method = self.runtime.split(
            "def _capture_job_operation_params", 1
        )[1].split("def _get_batch_execution_config", 1)[0]

        self.assertIn("panel_ids = list(self.workflow.operation_ids())", method)
        self.assertIn("job_ids = list(getattr(job, \"workflow_ids\"", method)
        self.assertIn("if not panel_ids and job_ids:", method)
        self.assertIn("return", method)
        self.assertIn("job.set_workflow(panel_ids)", method)

    def test_batch_still_uses_job_workflow_as_execution_source(self):
        source = (
            ROOT / "noark5_workflow" / "core" / "job_runner.py"
        ).read_text(encoding="utf-8")
        self.assertIn("job.workflow_ids", source)


if __name__ == "__main__":
    unittest.main()
