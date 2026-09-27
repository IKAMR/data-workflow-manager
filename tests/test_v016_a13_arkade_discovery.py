from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.external_evidence.arkade5_discovery import (
    _walk_report_candidates,
    discover_arkade5_reports_in_roots,
)


class V016A13ArkadeDiscoveryTests(unittest.TestCase):
    @staticmethod
    def _write_valid_report(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "Summary": {
                    "DateOfTesting": "2026-09-27",
                    "NumberOfTestsRun": 1,
                    "NumberOfErrors": 0,
                    "NumberOfWarnings": 0,
                },
                "TestsResults": [{"TestId": "N5.01"}],
            }),
            encoding="utf-8",
        )

    def test_discovers_generic_testrapport_below_arkade5_version_folder(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "job"
            report = (
                root
                / "repository_operations"
                / "arkade5_v2.12.3"
                / "folder"
                / "1543_010_testrapport.json"
            )
            self._write_valid_report(report)

            found = discover_arkade5_reports_in_roots(
                work_operations=root / "repository_operations" / "dwm" / "b09",
                work_root=root,
                source_root=root / "content" / "sip" / "content",
            )

            self.assertEqual([item.path for item in found], [report.resolve()])

    def test_document_payload_directories_are_pruned_case_independently(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "job"
            keep = root / "repository_operations" / "arkade5_v2.12.3" / "folder"
            keep.mkdir(parents=True)

            for dirname in ("DOKUMENT", "dokument", "DOKUMENTER", "dokumenter"):
                report = root / dirname / "arkade-testrapport.json"
                self._write_valid_report(report)

            candidates = list(_walk_report_candidates(
                root,
                max_depth=8,
                prune_heavy=True,
            ))
            candidate_text = {str(path) for path in candidates}

            for dirname in ("DOKUMENT", "dokument", "DOKUMENTER", "dokumenter"):
                self.assertFalse(any(dirname in value for value in candidate_text))

    def test_testrapport_name_is_plausible_even_without_arkade_word(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = root / "reports" / "1543_010_testrapport.json"
            self._write_valid_report(report)

            candidates = list(_walk_report_candidates(
                root,
                max_depth=4,
                prune_heavy=True,
            ))
            self.assertEqual(candidates, [report])


if __name__ == "__main__":
    unittest.main()
