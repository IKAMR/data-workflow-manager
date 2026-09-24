from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from noark5_workflow.external_evidence.arkade5_integration_health import (
    build_arkade5_integration_health,
)

ROOT = Path(__file__).resolve().parents[1]
OLD_COMMIT = "40a32ee0ae84ddf44d1f3c35f1860567ca262733"
NEW_COMMIT = "b27136ede491d3ec8b9e0ec9973ba455a0febbdf"


class V015A15Arkade2131Tests(unittest.TestCase):
    def test_base_catalog_remains_verified_2130(self):
        catalog = json.loads(
            (ROOT / "config/noark5/external/arkade5_test_catalog.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(catalog["arkade_version"], "2.13.0")
        self.assertEqual(catalog["source"]["commit"], OLD_COMMIT)
        self.assertEqual(
            catalog["summary"]["implemented_test_count"], 54
        )

    def test_release_delta_pins_2131(self):
        delta = json.loads(
            (
                ROOT / "config/noark5/external/"
                "arkade5_release_delta_2_13_1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(delta["current_arkade_version"], "2.13.1")
        self.assertEqual(delta["current_arkade_commit"], NEW_COMMIT)
        self.assertFalse(delta["semantic_catalog_changed"])
        self.assertFalse(delta["mapping_changed"])
        self.assertEqual(delta["noark5_test_implementations_changed"], 0)

    def test_runtime_affected_ids_are_exact(self):
        delta = json.loads(
            (
                ROOT / "config/noark5/external/"
                "arkade5_release_delta_2_13_1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            set(delta["runtime_affected_test_ids"]),
            {"N5.28", "N5.30", "N5.32", "N5.33", "N5.64"},
        )
        self.assertEqual(
            set(delta["inspected_not_runtime_affected_test_ids"]),
            {"N5.29", "N5.34"},
        )

    def test_mapping_counts_remain_unchanged(self):
        mapping = json.loads(
            (ROOT / "config/noark5/external/dwm_arkade5_mapping.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(mapping["arkade_version"], "2.13.0")
        self.assertEqual(mapping["summary"], {
            "equivalent": 1,
            "partial": 21,
            "complementary": 19,
            "arkade_only": 13,
            "arkade_test_count": 54,
            "dwm_only_count": 14,
        })

    def test_integration_health_is_ok_and_exposes_2131(self):
        result = build_arkade5_integration_health()
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["arkade_version"], "2.13.0")
        self.assertEqual(result["arkade_source_commit"], OLD_COMMIT)
        self.assertEqual(result["current_arkade_version"], "2.13.1")
        self.assertEqual(
            result["current_arkade_source_commit"], NEW_COMMIT
        )

    def test_profile_registers_release_delta(self):
        profile = json.loads(
            (ROOT / "config/noark5/profile.json")
            .read_text(encoding="utf-8")
        )
        self.assertIn(
            "config/noark5/external/"
            "arkade5_release_delta_2_13_1.json",
            profile["definitions"]["external_mappings"],
        )
        self.assertIn(
            "docs/ARKADE5-V2.13.1-CHANGE-IMPACT.md",
            profile["documentation"],
        )
        self.assertTrue(
            profile["capabilities"]["arkade_release_delta_tracking"]
        )

    def test_version_has_not_regressed_before_a15(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        if re.search(r'VERSION\s*=\s*"0\.1\.5"', version):
            return
        match = re.search(
            r'VERSION\s*=\s*"0\.1\.5-a(\d+)(?:\.\d+)*"',
            version,
        )
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 15)


if __name__ == "__main__":
    unittest.main()
