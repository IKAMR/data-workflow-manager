from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A11Fix1ActiveDepotAssessmentTests(unittest.TestCase):
    def test_active_job_uses_effective_work_operations(self):
        text = (
            ROOT / "gui" / "persistent_app_a43.py"
        ).read_text(encoding="utf-8")
        method = text.split(
            "def _open_depot_assessment", 1
        )[1].split(
            "def run_gui", 1
        )[0]

        self.assertIn('getattr(job, "_effective_work_operations", None)', method)
        self.assertIn('or getattr(job, "work_operations", None)', method)
        self.assertIn("DepotAssessmentDialog(", method)
        self.assertIn("work_operations=work_operations", method)

    def test_dialog_is_brought_to_front(self):
        text = (
            ROOT / "gui" / "persistent_app_a43.py"
        ).read_text(encoding="utf-8")
        method = text.split(
            "def _open_depot_assessment", 1
        )[1].split(
            "def run_gui", 1
        )[0]

        self.assertIn("dialog.lift()", method)
        self.assertIn("dialog.focus_force()", method)


if __name__ == "__main__":
    unittest.main()
