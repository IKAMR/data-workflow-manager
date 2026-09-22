from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A6Fix2WorkflowGuardTests(unittest.TestCase):
    def test_reset_restores_configured_noark5_workflow_for_empty_job(self):
        text = (
            ROOT / "gui" / "persistent_app_a38.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _restore_default_workflow_if_empty", text)
        self.assertIn('self.settings.get(', text)
        self.assertIn('"noark5_discovery_workflow"', text)
        self.assertIn('workflow_sequence_by_id("noark5_standard")', text)
        self.assertIn("job.set_workflow(sequence.operation_ids)", text)

    def test_batch_preflight_blocks_zero_operation_jobs(self):
        text = (
            ROOT / "gui" / "persistent_app_a38.py"
        ).read_text(encoding="utf-8")
        method = text.split("def _start_all_jobs", 1)[1].split(
            "def _get_app_work_subfolder", 1
        )[0]
        self.assertIn("0 operasjoner i workflow", method)
        self.assertIn("messagebox.showwarning(", method)
        self.assertIn("super()._start_all_jobs()", method)


if __name__ == "__main__":
    unittest.main()
