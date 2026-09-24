from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.external_evidence.arkade5_acceptance import (
    build_arkade5_practical_acceptance,
    write_arkade5_practical_acceptance,
)

ROOT = Path(__file__).resolve().parents[1]


class V015A13ArkadePracticalAcceptanceTests(unittest.TestCase):
    def _make_import(self, work: Path) -> None:
        import_id = "20260923-abc123"
        base = work / "external_evidence" / "arkade5" / import_id
        source = base / "source" / "arkade5_v2.13.0_report.json"
        normalized = base / "normalized" / "arkade5_results.json"
        source.parent.mkdir(parents=True)
        normalized.parent.mkdir(parents=True)
        source.write_text('{"Summary":{},"TestsResults":[]}', encoding="utf-8")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        normalized.write_text(json.dumps({
            "format_version": 2,
            "source_version": "2.13.0",
            "summary": {},
            "tests": [{"test_id": "N5.30", "source_status": "error", "number_of_errors": 1, "results": []}],
        }), encoding="utf-8")
        manifest = {
            "format_version": 2,
            "import_id": import_id,
            "source": {"original_name": source.name, "sha256": digest, "preserved_file": str(source.relative_to(work))},
            "normalized_file": str(normalized.relative_to(work)),
            "reconciliation_file": None,
        }
        (base / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_no_imports_is_not_ready(self):
        with tempfile.TemporaryDirectory() as td:
            result = build_arkade5_practical_acceptance(work_operations=Path(td))
            self.assertEqual(result["status"], "NOT_READY")

    def test_intact_import_is_ready_even_when_arkade_reports_error(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            self._make_import(work)
            result = build_arkade5_practical_acceptance(work_operations=work)
            self.assertEqual(result["status"], "READY")
            self.assertEqual(result["summary"]["blocking_issues"], 0)
            self.assertEqual(result["imports"][0]["arkade_error_test_count"], 1)

    def test_source_hash_mismatch_blocks_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            self._make_import(work)
            source = next((work / "external_evidence/arkade5").glob("*/source/*.json"))
            source.write_text("changed", encoding="utf-8")
            result = build_arkade5_practical_acceptance(work_operations=work)
            self.assertEqual(result["status"], "NOT_READY")
            self.assertTrue(any("SHA-256" in row["detail"] for row in result["blocking_issues"]))

    def test_acceptance_can_be_materialized(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / "work"
            work.mkdir()
            self._make_import(work)
            output = Path(td) / "acceptance.json"
            write_arkade5_practical_acceptance(output, work_operations=work)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "READY")

    def test_profile_registers_practical_acceptance(self):
        profile = json.loads((ROOT / "config/noark5/profile.json").read_text(encoding="utf-8"))
        self.assertIn("config/noark5/external/arkade5_practical_acceptance_contract.json", profile["definitions"]["external_mappings"])
        self.assertIn("docs/ARKADE5-PRACTICAL-ACCEPTANCE.md", profile["documentation"])
        self.assertTrue(profile["capabilities"]["arkade_practical_acceptance"])

    def test_version_has_not_regressed_before_a13(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.\d+)*)?"', version)
        self.assertIsNotNone(match)
        release = tuple(map(int, match.group(1, 2, 3)))
        self.assertGreaterEqual(release, (0, 1, 5))
        if release == (0, 1, 5) and match.group(4) is not None:
            self.assertGreaterEqual(int(match.group(4)), 13)


if __name__ == "__main__":
    unittest.main()
