from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A10Fix1ControlOverviewParentTests(unittest.TestCase):
    def test_jobs_window_is_preferred_parent(self):
        text = (
            ROOT / "gui" / "persistent_app_a42.py"
        ).read_text(encoding="utf-8")
        method = text.split(
            "def _open_validation_overview", 1
        )[1].split(
            "def _control_overview_closed", 1
        )[0]

        self.assertIn("parent = self", method)
        self.assertIn("parent = self.jobs_window", method)
        self.assertIn("Noark5ControlOverviewDialog(", method)
        self.assertIn("dialog.lift()", method)
        self.assertIn("dialog.focus_force()", method)

    def test_dialog_is_not_forced_modal(self):
        text = (
            ROOT / "gui" / "persistent_app_a42.py"
        ).read_text(encoding="utf-8")
        method = text.split(
            "def _open_validation_overview", 1
        )[1].split(
            "def _control_overview_closed", 1
        )[0]
        self.assertNotIn("grab_set()", method)


if __name__ == "__main__":
    unittest.main()
