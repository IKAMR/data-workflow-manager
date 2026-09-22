from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A10RuntimeContractTests(unittest.TestCase):
    def test_main_activates_a42(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a42 import run_gui", text)

    def test_control_overview_opens_in_app_dialog(self):
        text = (
            ROOT / "gui" / "persistent_app_a42.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Noark5ControlOverviewDialog", text)
        self.assertIn("def _open_validation_overview", text)

    def test_dialog_preserves_html_navigation(self):
        text = (
            ROOT / "gui" / "noark5_control_overview_dialog.py"
        ).read_text(encoding="utf-8")
        self.assertIn('text="HTML-oversikt"', text)
        self.assertIn('text="Åpne"', text)
        self.assertIn("filter_rows", text)


if __name__ == "__main__":
    unittest.main()
