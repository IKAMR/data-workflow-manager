from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A6Fix3AuthoritativeJobStateTests(unittest.TestCase):
    def setUp(self):
        self.text = (
            ROOT / "gui" / "persistent_app_a38.py"
        ).read_text(encoding="utf-8")

    def test_save_does_not_capture_transient_gui_workflow(self):
        method = self.text.split(
            "def _capture_job_operation_params", 1
        )[1].split("def _sync_visible_workflow_from_job", 1)[0]
        self.assertIn("return", method)
        self.assertNotIn("job.set_workflow", method)

    def test_main_header_reads_job_workflow_not_panel_workflow(self):
        method = self.text.split(
            "def _refresh_active_job_label", 1
        )[1].split("def _refresh_job_list_projection", 1)[0]
        self.assertIn('getattr(job, "workflow_ids"', method)
        self.assertNotIn("self.workflow.operation_ids()", method)

    def test_batch_repairs_stale_visible_panel_from_job_before_start(self):
        method = self.text.split(
            "def _start_all_jobs", 1
        )[1].split("def _get_app_work_subfolder", 1)[0]
        self.assertIn("self._sync_visible_workflow_from_job()", method)
        self.assertIn("super()._start_all_jobs()", method)

    def test_active_joblist_is_projected_to_main_status_bar(self):
        self.assertIn("self.status_bar.set_job_list(self.job_list_path)", self.text)


if __name__ == "__main__":
    unittest.main()
