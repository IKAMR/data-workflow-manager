from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noark5_workflow.external_evidence.depot_arkade5 import (
    add_arkade5_review_points,
    build_arkade5_depot_evidence,
    inject_arkade5_html,
)


class V015A5ArkadeDepotReportTests(unittest.TestCase):
    def test_all_imports_are_kept_as_separate_evidence_groups(self):
        manifests = [
            {"import_id": "one", "source": {"original_name": "one.json", "sha256": "1"}},
            {"import_id": "two", "source": {"original_name": "two.json", "sha256": "2"}},
        ]
        normalized = {
            "source_version": "2.13.0",
            "summary": {"date_of_testing": "2026-09-01", "number_of_tests_run": 1},
            "tests": [{"test_id": "N5.30", "source_status": "ok", "number_of_errors": 0, "results": []}],
        }
        model = {"technical_validation": {"tests": [{"test_id": "kdrs.c17"}]}}
        with patch("noark5_workflow.external_evidence.depot_arkade5.list_arkade5_imports", return_value=manifests), patch(
            "noark5_workflow.external_evidence.depot_arkade5.load_arkade5_import",
            return_value={"normalized": normalized, "reconciliation": None},
        ):
            result = build_arkade5_depot_evidence(work_operations="x", depot_model=model)
        self.assertEqual(result["summary"]["imports"], 2)
        self.assertEqual([row["import_id"] for row in result["imports"]], ["one", "two"])

    def test_external_errors_become_review_points_not_internal_status(self):
        model = {"technical_validation": {"status": "ok"}, "deviations": []}
        external = {"summary": {"imports": 1, "arkade_errors": 2, "arkade_warnings": 0, "covered_by_arkade": 3}}
        add_arkade5_review_points(model, external)
        self.assertEqual(model["technical_validation"]["status"], "ok")
        categories = {row["category"] for row in model["deviations"]}
        self.assertIn("arkade5_external_errors", categories)
        self.assertIn("arkade5_fills_dwm_gaps", categories)

    def test_html_gets_external_validation_section(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.html"
            path.write_text("<html><body><h1>Rapport</h1></body></html>", encoding="utf-8")
            model = {
                "external_validation": {
                    "arkade5": {
                        "summary": {"imports": 1, "covered_by_arkade": 4},
                        "imports": [{
                            "import_id": "i1",
                            "date_of_testing": "2026-09-01",
                            "source_version": "2.13.0",
                            "coverage": {"summary": {"covered_by_arkade": 4, "covered_by_both": 3, "arkade_errors": 1, "arkade_warnings": 0}},
                        }],
                    }
                }
            }
            inject_arkade5_html(path, model)
            text = path.read_text(encoding="utf-8")
            self.assertIn("Ekstern validering – Arkade 5", text)
            self.assertIn("i1", text)
            self.assertIn("2.13.0", text)

    def test_report_operation_attaches_external_evidence(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "noark5_workflow" / "operations" / "build_noark5_depot_report.py").read_text(encoding="utf-8")
        self.assertIn("attach_arkade5_to_depot_model", text)
        self.assertIn("inject_arkade5_html", text)


if __name__ == "__main__":
    unittest.main()
