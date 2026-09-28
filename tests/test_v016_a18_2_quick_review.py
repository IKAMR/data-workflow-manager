from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A182QuickReviewTests(unittest.TestCase):
    def test_gui_has_direct_plus_minus_pending_controls(self):
        source = (ROOT / "gui/depot_result_center_a18_2.py").read_text(encoding="utf-8")
        self.assertIn('text="+"', source)
        self.assertIn('text="−"', source)
        self.assertIn('text="?"', source)
        self.assertIn('"rejected"', source)
        self.assertIn('_PeriodReviewDialog', source)

    def test_minus_keeps_comment_requirement(self):
        source = (ROOT / "gui/depot_result_center_a18_2.py").read_text(encoding="utf-8")
        self.assertIn('self._a182_save_status(index, "rejected", comment)', source)
        review = (ROOT / "noark5_workflow/analysis/depot_review_status.py").read_text(encoding="utf-8")
        self.assertIn('if status == "rejected" and not comment:', review)

    def test_archive_cards_show_period_review_marker(self):
        source = (ROOT / "gui/depot_result_center_a18_2.py").read_text(encoding="utf-8")
        self.assertIn('Periodevurdering:', source)
        self.assertIn('_a182_refresh_all_card_statuses', source)

    def test_runtime_and_version_wiring(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        chain = (ROOT / "gui" / "persistent_app_a18_3.py").read_text(encoding="utf-8")
        self.assertIn("from .persistent_app_a18_2 import WorkflowApp as A18_2WorkflowApp", chain)
        self.assertRegex(version, r'VERSION = \"0\.1\.6-a18\.[2-9][0-9]*\"')


if __name__ == "__main__":
    unittest.main()
