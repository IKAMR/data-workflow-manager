from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A2DepotAssessmentGuiTests(unittest.TestCase):
    def test_main_uses_current_runtime_chain(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a21", main)
        a21 = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        a20 = (ROOT / "gui" / "persistent_app_a20.py").read_text(encoding="utf-8")
        self.assertIn("A20WorkflowApp", a21)
        self.assertIn("A19WorkflowApp", a20)

    def test_a19_extends_a18_and_keeps_results_action(self):
        a19 = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")
        a18 = (ROOT / "gui" / "persistent_app_a18.py").read_text(encoding="utf-8")
        a17 = (ROOT / "gui" / "persistent_app_a17.py").read_text(encoding="utf-8")

        self.assertIn("A18WorkflowApp", a19)
        self.assertIn("A17WorkflowApp", a18)
        self.assertIn("set_aux_action", a17)
        self.assertIn('"Resultater"', a17)
        self.assertIn("self._show_raw_results", a17)

    def test_dialog_exposes_all_four_existing_statuses(self):
        dialog = (ROOT / "gui" / "depot_assessment_dialog.py").read_text(encoding="utf-8")
        for status in (
            "accepted",
            "accepted_with_deviation",
            "requires_clarification",
            "new_extraction_required",
        ):
            self.assertIn(status, dialog)

    def test_dialog_uses_a1_assessment_service_and_identity(self):
        dialog = (ROOT / "gui" / "depot_assessment_dialog.py").read_text(encoding="utf-8")
        a19 = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")
        self.assertIn("record_depot_assessment", dialog)
        self.assertIn("load_depot_assessment", dialog)
        self.assertIn("current_user_identity", a19)


if __name__ == "__main__":
    unittest.main()
