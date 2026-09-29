from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _assert_version_at_least(testcase, version_text, alpha, sub=0):
    match = re.search(r'0\.1\.6-a(\d+)(?:\.(\d+))?', version_text)
    testcase.assertIsNotNone(match)
    actual_alpha = int(match.group(1))
    actual_sub = None if match.group(2) is None else int(match.group(2))
    testcase.assertTrue(actual_alpha > alpha or (actual_alpha == alpha and (actual_sub is None or actual_sub >= sub)))


class A214FormatLayoutTests(unittest.TestCase):
    def test_runtime_wires_a214(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        _assert_version_at_least(self, version, 21, 4)

    def test_overview_formats_are_count_first(self):
        source = (ROOT / "gui" / "depot_result_center_a21_4.py").read_text(encoding="utf-8")
        self.assertIn("count", source)

    def test_pronom_table_owns_full_width_and_protects_count_column(self):
        source = (ROOT / "gui" / "depot_result_center_a21_4.py").read_text(encoding="utf-8")
        self.assertIn("grid_columnconfigure", source)
        self.assertIn("Antall", source)

    def test_archive_parts_are_not_changed_in_this_step(self):
        source = (ROOT / "gui" / "depot_result_center_a21_4.py").read_text(encoding="utf-8")
        self.assertNotIn("class DepotResultCenterDialogA214ArchiveParts", source)


if __name__ == "__main__":
    unittest.main()
