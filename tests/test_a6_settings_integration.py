from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A6SettingsIntegrationTests(unittest.TestCase):
    def test_work_output_is_inside_scrollable_body(self):
        text = (ROOT / "gui" / "settings_dialog.py").read_text(encoding="utf-8")
        self.assertIn('text="Work-output"', text)
        self.assertIn('text="App-undermappe i Work"', text)

        section = text.split('text="Work-output"', 1)[1].split("tools =", 1)[0]
        self.assertIn("body,", section)

    def test_a24_no_longer_builds_duplicate_fixed_section(self):
        text = (ROOT / "gui" / "settings_dialog_a24.py").read_text(encoding="utf-8")
        self.assertIn("from .settings_dialog import SettingsDialog", text)
        self.assertNotIn("CTkFrame", text)
        self.assertNotIn("grid_slaves", text)

    def test_setting_is_loaded_and_collected_once(self):
        text = (ROOT / "gui" / "settings_dialog.py").read_text(encoding="utf-8")
        self.assertIn("self.app_work_subfolder_var = ctk.StringVar", text)
        self.assertIn('"app_work_subfolder": validate_app_work_subfolder(', text)


if __name__ == "__main__":
    unittest.main()
