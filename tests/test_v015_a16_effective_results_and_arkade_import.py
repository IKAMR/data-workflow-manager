
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from gui.result_history_dialog import raw_result_path_for_job
from noark5_workflow.app import build_registry
from noark5_workflow.external_evidence.arkade5_discovery import (
    import_discovered_arkade5_reports,
)
from app.workflow_sequences import workflow_sequence_by_id


class V015A16Tests(unittest.TestCase):
    def test_raw_results_use_effective_work_operations(self):
        job = SimpleNamespace(
            work_operations=Path("X:/base"),
            _effective_work_operations=Path("X:/base/dwm/a01"),
        )
        self.assertEqual(
            raw_result_path_for_job(job),
            Path("X:/base/dwm/a01/wf/results/raw-results.jsonl"),
        )

    def test_raw_results_fallback_to_base_work_operations(self):
        job = SimpleNamespace(work_operations=Path("X:/base"))
        self.assertEqual(
            raw_result_path_for_job(job),
            Path("X:/base/wf/results/raw-results.jsonl"),
        )

    def test_registry_contains_arkade_import_operation(self):
        registry = build_registry()
        operation = registry.get("import_arkade5_reports")
        self.assertEqual(
            operation.definition.name,
            "Finn/importer Arkade 5-resultater",
        )

    def test_standard_sequence_imports_arkade_before_views(self):
        seq = workflow_sequence_by_id("noark5_standard")
        self.assertIsNotNone(seq)
        ids = list(seq.operation_ids)
        self.assertIn("import_arkade5_reports", ids)
        self.assertLess(
            ids.index("run_noark5_xpath_tests_2026"),
            ids.index("import_arkade5_reports"),
        )
        self.assertLess(
            ids.index("import_arkade5_reports"),
            ids.index("compose_noark5_views"),
        )

    def test_discovery_import_and_duplicate_skip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / "repository_operations" / "dwm" / "a01"
            reports = root / "arkade-testrapporter_20260923200946"
            reports.mkdir(parents=True)
            report = reports / "arkade-testrapport_20260923200946.json"
            report.write_text(
                json.dumps({
                    "Summary": {
                        "DateOfTesting": "23. september 2026",
                        "NumberOfTestsRun": 1,
                    },
                    "TestsResults": [{
                        "TestId": "N5.01",
                        "TestName": "Test",
                        "TestType": "Test",
                        "HasResults": False,
                        "NumberOfErrors": 0,
                        "ResultSet": None,
                    }],
                }),
                encoding="utf-8",
            )

            first = import_discovered_arkade5_reports(
                work_operations=work,
                work_root=root,
                source_root=None,
            )
            self.assertEqual(first["found"], 1)
            self.assertEqual(first["imported"], 1)
            self.assertEqual(first["failed"], 0)

            second = import_discovered_arkade5_reports(
                work_operations=work,
                work_root=root,
                source_root=None,
            )
            self.assertEqual(second["found"], 1)
            self.assertEqual(second["imported"], 0)
            self.assertEqual(second["skipped"], 1)

    def test_no_report_is_successful_empty_discovery(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = import_discovered_arkade5_reports(
                work_operations=root / "work",
                work_root=root,
                source_root=None,
            )
            self.assertEqual(result["found"], 0)
            self.assertEqual(result["imported"], 0)
            self.assertEqual(result["failed"], 0)


if __name__ == "__main__":
    unittest.main()
