from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A2111ArchiveQueuePeriodFixTests(unittest.TestCase):
    def test_short_name_searches_nested_archive_part_identity(self):
        source = (ROOT / "gui" / "depot_result_center_a21_11.py").read_text(encoding="utf-8")
        self.assertIn('identity = row.get("archive_part") or {}', source)
        self.assertIn('for source in (identity, row):', source)

    def test_period_reuses_same_materialized_series_as_period_profiles(self):
        source = (ROOT / "gui" / "depot_result_center_a21_11.py").read_text(encoding="utf-8")
        self.assertIn('for kind in ("folder", "journal", "document_description"):', source)
        self.assertIn('series = self._series(row, kind) or {}', source)
        self.assertIn('return f"{min(years)}–{max(years)}"', source)

    def test_short_titles_are_not_duplicated(self):
        source = (ROOT / "gui" / "depot_result_center_a21_11.py").read_text(encoding="utf-8")
        self.assertIn('if len(text) <= 28:', source)
        self.assertIn('return ""', source)


if __name__ == "__main__":
    unittest.main()
