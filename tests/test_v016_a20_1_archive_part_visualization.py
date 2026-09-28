from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class A201ArchivePartVisualizationTests(unittest.TestCase):
    def test_a201_is_additive_over_a195(self):
        text = (ROOT / "gui" / "depot_result_center_a20_1.py").read_text(encoding="utf-8")
        self.assertIn("DepotResultCenterDialogA19_5", text)
        self.assertIn("_a201_place_period_profile_last", text)

    def test_a201_uses_semantic_series_colours(self):
        text = (ROOT / "gui" / "depot_result_center_a20_1.py").read_text(encoding="utf-8")
        self.assertIn('theme.CATEGORY_COLORS["Innhold"]', text)
        self.assertIn('theme.CATEGORY_COLORS["Metadata"]', text)
        self.assertIn("theme.BLUE", text)

    def test_a201_keeps_period_review_live(self):
        text = (ROOT / "gui" / "depot_result_center_a20_1.py").read_text(encoding="utf-8")
        self.assertIn("super()._show_archive_part(index)", text)
        self.assertIn("super()._a195_render_fact_profile(index)", text)


if __name__ == "__main__":
    unittest.main()
