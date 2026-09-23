
from __future__ import annotations

import re
import unittest
from pathlib import Path

from noark5_workflow.external_evidence.arkade5_gap_analysis import (
    build_gap_overlap_analysis,
)


ROOT = Path(__file__).resolve().parents[1]


class V015A9ArkadeGapOverlapTests(unittest.TestCase):
    def test_documented_mapping_materializes_expected_counts(self):
        model = build_gap_overlap_analysis()
        summary = model["summary"]
        self.assertEqual(summary["arkade_test_count"], 54)
        self.assertEqual(summary["equivalent"], 1)
        self.assertEqual(summary["partial"], 21)
        self.assertEqual(summary["complementary"], 19)
        self.assertEqual(summary["arkade_only"], 13)
        self.assertEqual(summary["dwm_only"], 14)
        self.assertEqual(summary["dwm_gaps_covered_by_arkade"], 13)
        self.assertEqual(summary["overlap_control_areas"], 41)

    def test_known_real_gaps_are_explicit(self):
        model = build_gap_overlap_analysis()
        gaps = set(model["dwm_gaps_covered_by_arkade"])
        self.assertEqual(gaps, {
            "N5.01", "N5.02", "N5.28", "N5.30", "N5.32", "N5.33",
            "N5.34", "N5.47", "N5.48", "N5.51", "N5.62", "N5.63",
            "N5.64",
        })

    def test_namespaces_are_not_collapsed(self):
        model = build_gap_overlap_analysis()
        area = next(
            row for row in model["arkade_control_areas"]
            if row["arkade_test_id"] == "N5.24"
        )
        self.assertEqual(area["namespace_id"], "arkade:N5.24")
        self.assertEqual(area["dwm"][0]["namespace_id"], "dwm:kdrs.c22")
        self.assertEqual(area["dwm"][0]["legacy_namespace_id"], "kdrs:N5.24")

    def test_mapping_consistency_is_green(self):
        consistency = build_gap_overlap_analysis()["consistency"]
        self.assertTrue(consistency["mapping_summary_matches"])
        self.assertTrue(consistency["catalog_contains_all_mapped_arkade_ids"])
        self.assertEqual(consistency["mapped_dwm_ids_missing_from_catalog"], [])

    def test_version_has_not_regressed_before_a9(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(
            r'VERSION\s*=\s*"0\.1\.5-a(\d+)(?:\.\d+)*"',
            version,
        )
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 9)


if __name__ == "__main__":
    unittest.main()
