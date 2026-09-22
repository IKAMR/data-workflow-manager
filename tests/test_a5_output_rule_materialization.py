from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A5OutputRuleMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (
            ROOT / "gui" / "persistent_app_a37.py"
        ).read_text(encoding="utf-8")

    def test_explicit_use_rule_materializes_effective_work_folders(self):
        method = self.runtime.split(
            "def _set_output_subfolder_rule(", 1
        )[1].split("def _open_jobs", 1)[0]
        self.assertIn("path.mkdir(parents=True, exist_ok=True)", method)

    def test_startup_load_path_remains_side_effect_free(self):
        a36 = (
            ROOT / "gui" / "persistent_app_a36.py"
        ).read_text(encoding="utf-8")
        method = a36.split(
            "def _apply_effective_work_operations", 1
        )[1].split("def _normalise_job_before_run", 1)[0]
        self.assertNotIn(".mkdir(", method)

    def test_storage_failure_is_returned_as_gui_error_not_startup_crash(self):
        method = self.runtime.split(
            "def _set_output_subfolder_rule(", 1
        )[1].split("def _open_jobs", 1)[0]
        self.assertIn("except OSError as exc", method)
        self.assertIn("Kunne ikke opprette Work-undermappene", method)


if __name__ == "__main__":
    unittest.main()
