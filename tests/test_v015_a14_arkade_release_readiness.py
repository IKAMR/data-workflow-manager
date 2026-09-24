from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.external_evidence.arkade5_release_readiness import (
    build_v015_release_readiness,
    write_v015_release_readiness,
)

ROOT = Path(__file__).resolve().parents[1]


class V015A14ArkadeReleaseReadinessTests(unittest.TestCase):
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
            "tests": [{
                "test_id": "N5.30",
                "source_status": "error",
                "number_of_errors": 1,
                "results": [],
            }],
        }), encoding="utf-8")

        (base / "manifest.json").write_text(json.dumps({
            "format_version": 2,
            "import_id": import_id,
            "source": {
                "original_name": source.name,
                "sha256": digest,
                "preserved_file": str(source.relative_to(work)),
            },
            "normalized_file": str(normalized.relative_to(work)),
            "reconciliation_file": None,
        }), encoding="utf-8")

    def _write_summary(self, path: Path, *, failed=0, errors=0) -> None:
        path.write_text(
            "TOTAL=100\nPASSED=100\n"
            f"FAILED={failed}\nERRORS={errors}\nSKIPPED=0\n",
            encoding="utf-8",
        )

    def test_all_three_gates_green_means_ready_for_release(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / "work"
            work.mkdir()
            self._make_import(work)
            summary = root / "summary.txt"
            self._write_summary(summary)
            result = build_v015_release_readiness(
                work_operations=work,
                test_summary_path=summary,
            )
            self.assertEqual(result["status"], "READY_FOR_V0.1.5")
            self.assertEqual(result["summary"]["blocked"], 0)

    def test_failed_test_suite_blocks_release(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / "work"
            work.mkdir()
            self._make_import(work)
            summary = root / "summary.txt"
            self._write_summary(summary, failed=1)
            result = build_v015_release_readiness(
                work_operations=work,
                test_summary_path=summary,
            )
            self.assertEqual(result["status"], "NOT_READY_FOR_V0.1.5")
            gate = next(
                row for row in result["gates"]
                if row["gate_id"] == "full_test_suite"
            )
            self.assertEqual(gate["status"], "BLOCKED")

    def test_missing_real_import_blocks_release(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / "work"
            work.mkdir()
            summary = root / "summary.txt"
            self._write_summary(summary)
            result = build_v015_release_readiness(
                work_operations=work,
                test_summary_path=summary,
            )
            self.assertEqual(result["status"], "NOT_READY_FOR_V0.1.5")

    def test_release_readiness_can_be_materialized(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / "work"
            work.mkdir()
            self._make_import(work)
            summary = root / "summary.txt"
            self._write_summary(summary)
            output = root / "readiness.json"
            write_v015_release_readiness(
                output,
                work_operations=work,
                test_summary_path=summary,
            )
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["status"],
                "READY_FOR_V0.1.5",
            )

    def test_profile_registers_release_readiness(self):
        profile = json.loads(
            (ROOT / "config/noark5/profile.json").read_text(encoding="utf-8")
        )
        self.assertIn(
            "config/noark5/external/arkade5_release_readiness_contract.json",
            profile["definitions"]["external_mappings"],
        )
        self.assertIn(
            "docs/ARKADE5-RELEASE-READINESS.md",
            profile["documentation"],
        )
        self.assertTrue(
            profile["capabilities"]["arkade_release_readiness_gate"]
        )

    def test_version_has_not_regressed_before_a14(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.\d+)*)?"', version)
        self.assertIsNotNone(match)
        release = tuple(map(int, match.group(1, 2, 3)))
        self.assertGreaterEqual(release, (0, 1, 5))
        if release == (0, 1, 5) and match.group(4) is not None:
            self.assertGreaterEqual(int(match.group(4)), 14)


if __name__ == "__main__":
    unittest.main()
