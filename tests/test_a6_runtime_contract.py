from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A6RuntimeContractTests(unittest.TestCase):
    def test_main_preserves_a37_and_activates_a38(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a37 import run_gui", main)
        self.assertIn("from gui.persistent_app_a38 import run_gui", main)

    def test_default_config_has_dwm_app_root(self):
        settings = (ROOT / "settings.py").read_text(encoding="utf-8")
        self.assertIn('"app_work_subfolder": "dwm"', settings)

    def test_a38_applies_app_root_before_job_rule(self):
        runtime = (
            ROOT / "gui" / "persistent_app_a38.py"
        ).read_text(encoding="utf-8")
        self.assertIn("effective_work_operations(", runtime)
        self.assertIn("self._get_app_work_subfolder()", runtime)

    def test_settings_exposes_blank_or_custom_app_root(self):
        dialog = (
            ROOT / "gui" / "settings_dialog.py"
        ).read_text(encoding="utf-8")
        self.assertIn("App-undermappe i Work", dialog)
        self.assertIn("Blank = bruk Work - operations direkte", dialog)


if __name__ == "__main__":
    unittest.main()
