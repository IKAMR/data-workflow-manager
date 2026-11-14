from pathlib import Path
import re
import unittest
from version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]


def _assert_version_at_least(testcase, version_text, alpha, sub=0):
    assert_v016_at_least(testcase, version_text, alpha, sub, consolidated_alpha=True)


class A216PeriodIndicatorTests(unittest.TestCase):
    def test_version_is_a216(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        _assert_version_at_least(self, version, 21, 6)

    def test_runtime_wires_a216_before_main_guard(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a21_6", source)

    def test_period_rows_have_breathing_room_before_start_year(self):
        source = (ROOT / "gui" / "depot_result_center_a21_6.py").read_text(encoding="utf-8")
        self.assertIn("Oppgitt", source)
        self.assertIn("Observert", source)
        self.assertIn("Vurdert", source)

    def test_period_indicator_uses_materialized_ranges_and_detached_outlier(self):
        source = (ROOT / "gui" / "depot_result_center_a21_6.py").read_text(encoding="utf-8")
        self.assertIn("2099", source)

    def test_archive_parts_not_overridden(self):
        source = (ROOT / "gui" / "depot_result_center_a21_6.py").read_text(encoding="utf-8")
        self.assertNotIn("A216ArchiveParts", source)


if __name__ == "__main__":
    unittest.main()
