from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A11AssessmentFlowTests(unittest.TestCase):
    def test_control_overview_has_direct_assessment_action(self):
        text = (
            ROOT / "gui" / "noark5_control_overview_dialog_a11.py"
        ).read_text(encoding="utf-8")
        self.assertIn('text="Vurder"', text)
        self.assertIn("DirectDepotAssessmentDialog", text)
        self.assertIn("report_path=report_path", text)

    def test_exact_report_is_loaded_not_latest_work_report(self):
        text = (
            ROOT / "gui" / "direct_depot_assessment_dialog.py"
        ).read_text(encoding="utf-8")
        self.assertIn("work_operations=None", text)
        self.assertIn("self._load_report(Path(report_path))", text)

    def test_live_depot_assessment_is_refreshed(self):
        text = (
            ROOT / "gui" / "noark5_control_overview_dialog_a11.py"
        ).read_text(encoding="utf-8")
        self.assertIn("load_depot_assessment", text)
        self.assertIn("Depotvurdering", text)
        self.assertIn("self.after_idle(self._refresh_rows)", text)

    def test_runtime_passes_current_user_identity(self):
        text = (
            ROOT / "gui" / "persistent_app_a43.py"
        ).read_text(encoding="utf-8")
        self.assertIn("identity = self.current_user_identity()", text)
        self.assertIn("user_identity=identity", text)


if __name__ == "__main__":
    unittest.main()
