import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.external_evidence.arkade5_discovery import (
    discover_arkade5_reports,
)


class A11Fix2ArkadeDiscoveryTests(unittest.TestCase):
    def test_discovers_valid_arkade5_noark5_json_but_not_generic_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = (
                root / "job" / "repository_operations" / "dwm" / "a03"
                / "noark5_reports" / "depot_validation" / "run"
                / "depot_validation_report.json"
            )
            report.parent.mkdir(parents=True)
            report.write_text("{}", encoding="utf-8")

            arkade = root / "job" / "repository_operations" / "arkade5_v2.13.0" / "report.json"
            arkade.parent.mkdir(parents=True)
            arkade.write_text(json.dumps({
                "Summary": {"DateOfTesting": "2026-02-26", "NumberOfTestsRun": 1},
                "TestsResults": [{"TestId": "N5.1"}],
            }), encoding="utf-8")

            other = root / "job" / "other.json"
            other.write_text(json.dumps({"hello": "world"}), encoding="utf-8")

            found = discover_arkade5_reports(report)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].path, arkade.resolve())

    def test_ignores_already_imported_external_evidence_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = (
                root / "job" / "repository_operations" / "dwm" / "a03"
                / "noark5_reports" / "depot_validation" / "run"
                / "depot_validation_report.json"
            )
            report.parent.mkdir(parents=True)
            report.write_text("{}", encoding="utf-8")

            copied = (
                root / "job" / "repository_operations" / "dwm" / "a03"
                / "external_evidence" / "arkade5" / "x" / "source" / "report.json"
            )
            copied.parent.mkdir(parents=True)
            copied.write_text(json.dumps({
                "Summary": {"NumberOfTestsRun": 1},
                "TestsResults": [{"TestId": "N5.1"}],
            }), encoding="utf-8")

            self.assertEqual(discover_arkade5_reports(report), [])


if __name__ == "__main__":
    unittest.main()
