from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StartupDisconnectedStorageA31Tests(unittest.TestCase):
    def test_loading_job_list_does_not_create_effective_work_directory(self):
        source = (ROOT / "gui" / "persistent_app_a36.py").read_text(encoding="utf-8")
        block = source.split(
            "def _apply_effective_work_operations", 1
        )[1].split("def _normalise_job_before_run", 1)[0]

        self.assertIn("job._effective_work_operations = effective", block)
        self.assertNotIn(".mkdir(", block)

    def test_restore_path_can_be_calculated_without_storage_side_effect(self):
        source = (ROOT / "gui" / "persistent_app_a36.py").read_text(encoding="utf-8")
        load_block = source.split(
            "def _load_job_list_file", 1
        )[1].split("def _open_jobs", 1)[0]

        self.assertIn("self._apply_effective_work_operations(job)", load_block)
        self.assertNotIn(".mkdir(", load_block)


if __name__ == "__main__":
    unittest.main()
