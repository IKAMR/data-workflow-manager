from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A10StorageStateTests(unittest.TestCase):

    def test_dialog_has_explicit_unavailable_storage_message(self):
        source = (ROOT / "gui" / "depot_assessment_dialog_a30.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("LAGRING UTILGJENGELIG", source)
        self.assertIn("Koble til / lås opp lagringen og prøv igjen.", source)
        self.assertIn("Dette betyr ikke at depotvalideringsrapporten mangler.", source)

    def test_expected_work_path_is_visible(self):
        source = (ROOT / "gui" / "depot_assessment_dialog_a30.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Forventet Work-bane:", source)
        self.assertIn("storage_unavailable_path", source)

    def test_report_actions_stay_disabled_without_report(self):
        source = (ROOT / "gui" / "depot_assessment_dialog_a30.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('self.result_views_button.configure(state="disabled")', source)
        self.assertIn('self.open_report_button.configure(state="disabled")', source)

    def test_manual_choose_report_is_not_disabled(self):
        source = (ROOT / "gui" / "depot_assessment_dialog_a30.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('choose_report_button.configure(state="disabled")', source)


if __name__ == "__main__":
    unittest.main()
