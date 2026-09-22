from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A6Fix4JobWorkflowRepairTests(unittest.TestCase):
    def setUp(self):
        self.text = (
            ROOT / "gui" / "persistent_app_a38.py"
        ).read_text(encoding="utf-8")

    def test_repair_is_narrow_to_noark5_historical_empty_jobs(self):
        method = self.text.split(
            "def _repair_invalid_empty_noark5_workflow", 1
        )[1].split(
            "def _repair_invalid_empty_noark5_workflows", 1
        )[0]

        self.assertIn('profile_id', method)
        self.assertIn('"noark5"', method)
        self.assertIn("_job_has_historical_execution(job)", method)
        self.assertIn("job.set_workflow(sequence.operation_ids)", method)

    def test_load_repairs_and_persists_legacy_corruption(self):
        method = self.text.split(
            "def _load_job_list_file", 1
        )[1].split(
            "def _write_job_list", 1
        )[0]

        self.assertIn("_repair_invalid_empty_noark5_workflows()", method)
        self.assertIn("super()._write_job_list(self.job_list_path)", method)

    def test_every_write_enforces_invariant(self):
        method = self.text.split(
            "def _write_job_list", 1
        )[1].split(
            "def _open_job", 1
        )[0]

        self.assertIn("_repair_invalid_empty_noark5_workflows()", method)
        self.assertIn("super()._write_job_list(path)", method)

    def test_open_and_batch_start_repair_before_use(self):
        open_method = self.text.split(
            "def _open_job", 1
        )[1].split(
            "def _create_job", 1
        )[0]
        self.assertIn("_repair_invalid_empty_noark5_workflow(job)", open_method)

        start_method = self.text.split(
            "def _start_all_jobs", 1
        )[1].split(
            "def _get_app_work_subfolder", 1
        )[0]
        self.assertIn("_repair_invalid_empty_noark5_workflows()", start_method)


if __name__ == "__main__":
    unittest.main()
