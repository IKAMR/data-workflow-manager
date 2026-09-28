from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _assert_version_at_least(testcase, version_text, alpha, sub=0):
    match = re.search(r'VERSION = "0\.1\.6-a(\d+)(?:\.(\d+))?"', version_text)
    testcase.assertIsNotNone(match)
    actual = (int(match.group(1)), int(match.group(2) or 0))
    testcase.assertGreaterEqual(actual, (alpha, sub))


class A195ArchiveFactProfileTests(unittest.TestCase):
    def test_runtime_wires_a195(self):
        self.assertIn("from gui.persistent_app_a19_5 import run_gui", (ROOT / "main.py").read_text(encoding="utf-8"))
        _assert_version_at_least(self, (ROOT / "version.py").read_text(encoding="utf-8"), 19, 5)

    def test_three_period_canvases_keep_original_columns(self):
        text = (ROOT / "gui" / "depot_result_center_a19_5.py").read_text(encoding="utf-8")
        self.assertIn('column=int(info.get("column", index))', text)
        self.assertIn('baseline + 6', text)

    def test_fact_profile_uses_materialized_per_part_controls(self):
        text = (ROOT / "gui" / "depot_result_center_a19_5.py").read_text(encoding="utf-8")
        for token in ("journalpost_type_counts", "journal_status_counts", "document_type_counts", "variant_format_counts"):
            self.assertIn(token, text)
        self.assertIn("Andre materialiserte metadata", text)
        self.assertIn("_sections_for_index(index)", text)


if __name__ == "__main__":
    unittest.main()
