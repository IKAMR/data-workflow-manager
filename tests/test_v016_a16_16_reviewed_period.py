from pathlib import Path
import unittest

from noark5_workflow.analysis.period_assessment import suggest_reviewed_period

ROOT = Path(__file__).resolve().parents[1]


class A1616ReviewedPeriodTests(unittest.TestCase):
    def test_suggestion_trims_small_outer_tails_and_document_only_2099(self):
        row = {
            "yearly_volume": {
                "folder": {"2007": 4, "2008": 2074, "2019": 1489, "2020": 15, "2099": 0},
                "journal": {"2007": 62, "2008": 7894, "2019": 15246, "2020": 410, "2099": 0},
                "document_description": {"2007": 82, "2008": 16381, "2020": 409, "2099": 11034},
                "document_object": {"2007": 48, "2008": 28331, "2020": 1152, "2099": 24007},
            }
        }
        self.assertEqual((2008, 2019), suggest_reviewed_period(row))

    def test_main_uses_a16_16_before_guard(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertLess(text.rfind("from gui.persistent_app_a16_16 import run_gui"), text.rfind('if __name__ == "__main__":'))

    def test_dialog_has_manual_and_suggested_period(self):
        text = (ROOT / "gui" / "depot_result_center_a16_16.py").read_text(encoding="utf-8")
        self.assertIn('text="Vurdert periode"', text)
        self.assertIn('text="Bruk forslag"', text)
        self.assertIn('text="Lagre"', text)
        self.assertIn('depot_period_assessment.json', text)

    def test_synthetic_all_row_not_used_as_archive_count(self):
        text = (ROOT / "gui" / "depot_result_center_a16_16.py").read_text(encoding="utf-8")
        self.assertIn('if not row.get("is_all_archive_parts")', text)
        self.assertIn('["archive_part_count"] = real', text)


if __name__ == "__main__":
    unittest.main()
