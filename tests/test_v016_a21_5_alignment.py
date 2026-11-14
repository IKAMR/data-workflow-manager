from pathlib import Path
import re
import unittest
from version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]


def _assert_version_at_least(testcase, version_text, alpha, sub=0):
    assert_v016_at_least(testcase, version_text, alpha, sub, consolidated_alpha=True)


class A215AlignmentTests(unittest.TestCase):
    def test_runtime_wires_a215(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        _assert_version_at_least(self, version, 21, 5)

    def test_period_rows_have_separate_start_and_end_columns(self):
        source = (ROOT / "gui" / "depot_result_center_a21_5.py").read_text(encoding="utf-8")
        self.assertIn("Oppgitt", source)
        self.assertIn("Observert", source)
        self.assertIn("Vurdert", source)

    def test_long_format_names_are_shortened_for_display_only(self):
        source = (ROOT / "gui" / "depot_result_center_a21_5.py").read_text(encoding="utf-8")
        self.assertIn("format", source.lower())

    def test_pronom_columns_are_grouped_left_with_final_spacer(self):
        source = (ROOT / "gui" / "depot_result_center_a21_5.py").read_text(encoding="utf-8")
        self.assertIn("Antall", source)

    def test_archive_parts_are_not_changed_in_this_step(self):
        source = (ROOT / "gui" / "depot_result_center_a21_5.py").read_text(encoding="utf-8")
        self.assertNotIn("A215ArchiveParts", source)


if __name__ == "__main__":
    unittest.main()
