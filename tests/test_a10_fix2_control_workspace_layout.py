from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A10Fix2ControlWorkspaceLayoutTests(unittest.TestCase):
    def test_dialog_has_workspace_context_and_detail_panels(self):
        text = (ROOT / "gui" / "noark5_control_overview_dialog.py").read_text(encoding="utf-8")
        self.assertIn("self.selected_row", text)
        self.assertIn("Faglig vurdering", text)
        self.assertIn("Kontroller", text)
        self.assertIn("self.detail_frame", text)


if __name__ == "__main__":
    unittest.main()
