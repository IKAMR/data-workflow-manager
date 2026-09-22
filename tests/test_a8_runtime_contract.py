from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A8RuntimeContractTests(unittest.TestCase):
    def test_main_activates_a40(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a40 import run_gui", text)

    def test_runtime_generates_overview_at_run_finish(self):
        text = (
            ROOT / "gui" / "persistent_app_a40.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _new_run_log", text)
        self.assertIn("finish_with_validation", text)
        self.assertIn("_write_run_validation_overview", text)

    def test_jobs_window_has_control_overview_action(self):
        text = (
            ROOT / "gui" / "jobs_window_a26.py"
        ).read_text(encoding="utf-8")
        self.assertIn('text="Kontrolloversikt"', text)

    def test_output_uses_configurable_run_log_role(self):
        text = (
            ROOT / "app" / "noark5_validation_overview.py"
        ).read_text(encoding="utf-8")
        self.assertIn("root = run_log_dir(settings)", text)
        self.assertNotIn("C:\\\\", text)
        self.assertNotIn("G:\\\\", text)


if __name__ == "__main__":
    unittest.main()
