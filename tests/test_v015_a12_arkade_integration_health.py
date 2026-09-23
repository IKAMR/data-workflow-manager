
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.external_evidence.arkade5_integration_health import (
    build_arkade5_integration_health,
    write_arkade5_integration_health,
)

ROOT = Path(__file__).resolve().parents[1]


class V015A12ArkadeIntegrationHealthTests(unittest.TestCase):
    def test_current_integration_health_is_ok(self):
        result = build_arkade5_integration_health()
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["summary"]["errors"], 0)
        self.assertGreaterEqual(result["summary"]["checks"], 10)

    def test_health_checks_locked_counts(self):
        result = build_arkade5_integration_health()
        by_id = {row["check_id"]: row for row in result["checks"]}
        self.assertEqual(by_id["arkade_catalog_count"]["actual"], 54)
        self.assertEqual(by_id["mapping_relation_counts"]["actual"], {
            "equivalent": 1,
            "partial": 21,
            "complementary": 19,
            "arkade_only": 13,
        })
        self.assertEqual(by_id["dwm_only_count"]["actual"], 14)

    def test_health_locks_version_and_commit(self):
        result = build_arkade5_integration_health()
        self.assertEqual(result["arkade_version"], "2.13.0")
        self.assertEqual(
            result["arkade_source_commit"],
            "40a32ee0ae84ddf44d1f3c35f1860567ca262733",
        )

    def test_health_report_can_be_written(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_arkade5_integration_health(
                Path(td) / "arkade5-integration-health.json"
            )
            result = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "OK")

    def test_profile_registers_closeout_contract(self):
        profile = json.loads(
            (ROOT / "config/noark5/profile.json").read_text(encoding="utf-8")
        )
        self.assertIn(
            "config/noark5/external/arkade5_integration_contract.json",
            profile["definitions"]["external_mappings"],
        )
        self.assertIn(
            "docs/ARKADE5-INTEGRATION-CONTRACT.md",
            profile["documentation"],
        )
        self.assertTrue(
            profile["capabilities"]["arkade_integration_health_check"]
        )

    def test_version_has_not_regressed_before_a12(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.5-a(\d+)(?:\.\d+)*"', version)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 12)


if __name__ == "__main__":
    unittest.main()
