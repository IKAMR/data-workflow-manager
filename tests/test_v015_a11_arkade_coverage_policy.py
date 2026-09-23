
from __future__ import annotations

import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from noark5_workflow.external_evidence.arkade5_coverage_policy import (
    load_arkade5_coverage_policy,
    validate_arkade5_coverage_policy,
)


ROOT = Path(__file__).resolve().parents[1]


class V015A11ArkadeCoveragePolicyTests(unittest.TestCase):
    def test_policy_matches_all_documented_arkade_only_gaps(self):
        result = validate_arkade5_coverage_policy()
        self.assertTrue(result["valid"])
        self.assertEqual(result["expected_gap_count"], 13)
        self.assertEqual(result["configured_gap_count"], 13)
        self.assertEqual(result["missing_from_policy"], [])
        self.assertEqual(result["extra_in_policy"], [])

    def test_all_gap_rows_use_arkade_and_defer_internal_implementation(self):
        policy = load_arkade5_coverage_policy()
        rows = policy["documented_dwm_gaps"]
        self.assertEqual(len(rows), 13)
        self.assertTrue(all(
            row["current_coverage_strategy"] == "use_arkade_external"
            for row in rows
        ))
        self.assertTrue(all(
            row["dwm_internal_implementation"] == "deferred"
            for row in rows
        ))

    def test_profile_registers_policy(self):
        profile = json.loads(
            (ROOT / "config/noark5/profile.json").read_text(encoding="utf-8")
        )
        self.assertIn(
            "config/noark5/external/arkade5_coverage_policy.json",
            profile["definitions"]["external_mappings"],
        )
        self.assertTrue(
            profile["capabilities"]["arkade_external_gap_coverage_policy"]
        )

    def test_portable_export_includes_gap_and_policy_knowledge(self):
        source = (
            ROOT
            / "noark5_workflow"
            / "external_evidence"
            / "arkade5_export.py"
        ).read_text(encoding="utf-8")
        self.assertIn("gap_overlap_model.json", source)
        self.assertIn("arkade5_coverage_policy.json", source)
        self.assertIn("gap_overlap_analysis.json", source)
        self.assertIn("coverage_policy_validation.json", source)
        self.assertIn("PACKAGE_FORMAT_VERSION = 2", source)

    def test_version_has_not_regressed_before_a11(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(
            r'VERSION\s*=\s*"0\.1\.5-a(\d+)(?:\.\d+)*"',
            version,
        )
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 11)


if __name__ == "__main__":
    unittest.main()
