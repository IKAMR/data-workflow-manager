import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.legacy_regression import build_legacy_regression_comparison

class A242LegacyRegressionTests(unittest.TestCase):

    def test_machine_comparison_matches_whole_and_archive_part(self):
        with tempfile.TemporaryDirectory() as td:
            results = Path(td)
            def write(test_id, values):
                (results / (test_id.replace(".", "_") + ".json")).write_text(
                    json.dumps({"values": values}), encoding="utf-8"
                )

            write("kdrs.u01", {"folders": {"count": 3}})
            write("kdrs.u02", {"archive_parts": [
                {"archive_part": {"system_id": "A", "index": 1}, "values": {"folder_count": 3}}
            ]})
            write("kdrs.c13", {
                "folder_count": 3,
                "_archive_parts": [
                    {"archive_part": {"system_id": "A"}, "values": {"folder_count": 3}}
                ]
            })

            contract = {
                "whole_extraction_comparisons": [
                    {"id":"folder_count","legacy_path":"folders.count","canonical_test":"kdrs.c13","canonical_path":"folder_count"}
                ],
                "archive_part_comparisons": [
                    {"id":"folder_count","legacy_path":"folder_count","canonical_test":"kdrs.c13","canonical_path":"folder_count"}
                ]
            }
            comparison = build_legacy_regression_comparison(results, contract)
            self.assertEqual(comparison["summary"]["checks"], 2)
            self.assertEqual(comparison["summary"]["matches"], 2)
            self.assertEqual(comparison["summary"]["status"], "match")

    def test_machine_comparison_reports_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            results = Path(td)
            def write(test_id, values):
                (results / (test_id.replace(".", "_") + ".json")).write_text(
                    json.dumps({"values": values}), encoding="utf-8"
                )

            write("kdrs.u01", {"folders": {"count": 3}})
            write("kdrs.u02", {"archive_parts": []})
            write("kdrs.c13", {"folder_count": 4, "_archive_parts": []})

            contract = {
                "whole_extraction_comparisons": [
                    {"id":"folder_count","legacy_path":"folders.count","canonical_test":"kdrs.c13","canonical_path":"folder_count"}
                ],
                "archive_part_comparisons": []
            }
            comparison = build_legacy_regression_comparison(results, contract)
            self.assertEqual(comparison["summary"]["mismatches"], 1)
            self.assertEqual(comparison["summary"]["status"], "review")

if __name__ == "__main__":
    unittest.main()
