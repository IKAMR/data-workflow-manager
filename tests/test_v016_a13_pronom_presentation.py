from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noark5_workflow.external_evidence.arkade5_pronom import (
    summarize_arkade5_pronom_statistics,
)
from noark5_workflow.external_evidence.depot_arkade5 import (
    build_arkade5_depot_evidence,
    inject_arkade5_html,
)


class V016A13PronomPresentationTests(unittest.TestCase):
    def test_summary_uses_statistics_only_and_documents_detailed_inventory(self):
        normalized = {
            "identification_engine": "Siegfried / PRONOM",
            "source": {"original_name": "stats.csv", "sha256": "abc"},
            "csv": {
                "fieldnames": ["Format-ID", "Filtype", "Formatversjon", "RAF-220301", "Antall"],
                "rows": [
                    {"Format-ID": "fmt/18", "Filtype": "PDF", "Formatversjon": "1.4", "RAF-220301": "Ja", "Antall": "10"},
                    {"Format-ID": "fmt/18", "Filtype": "PDF", "Formatversjon": "1.4", "RAF-220301": "Ja", "Antall": "2"},
                    {"Format-ID": "", "Filtype": "Ukjent", "Formatversjon": "", "RAF-220301": "", "Antall": "3"},
                ],
            },
        }
        manifest = {
            "pronom_evidence": {
                "detailed_file_inventory": {
                    "found": True,
                    "imported": False,
                    "original_name": "detail.csv",
                    "size_bytes": 123456,
                    "policy": "Ikke importert.",
                }
            }
        }
        result = summarize_arkade5_pronom_statistics(normalized, manifest=manifest)
        stats = result["statistics"]
        self.assertEqual(stats["row_count"], 3)
        self.assertEqual(stats["total_files"], 15)
        self.assertEqual(stats["unique_format_ids"], 1)
        self.assertEqual(stats["unidentified_files"], 3)
        self.assertEqual(stats["rows"][0]["format_id"], "fmt/18")
        self.assertTrue(result["detailed_file_inventory"]["found"])
        self.assertFalse(result["detailed_file_inventory"]["imported"])

    def test_depot_model_contains_pronom_summary_and_rows(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            normalized_rel = Path("external_evidence/arkade5/import-1/normalized/pronom_statistics.json")
            normalized_path = work / normalized_rel
            normalized_path.parent.mkdir(parents=True)
            normalized_path.write_text(json.dumps({
                "identification_engine": "Siegfried / PRONOM",
                "source": {"original_name": "stats.csv"},
                "csv": {
                    "fieldnames": ["Format-ID", "Filtype", "Formatversjon", "RAF-220301", "Antall"],
                    "rows": [
                        {"Format-ID": "fmt/18", "Filtype": "PDF", "Formatversjon": "1.4", "RAF-220301": "Ja", "Antall": "12"},
                        {"Format-ID": "fmt/111", "Filtype": "PDF/A", "Formatversjon": "1a", "RAF-220301": "Ja", "Antall": "8"},
                    ],
                },
            }), encoding="utf-8")

            manifest = {
                "import_id": "import-1",
                "source": {"original_name": "report.json", "sha256": "sha"},
                "normalized_file": "external_evidence/arkade5/import-1/normalized/arkade5_results.json",
                "pronom_evidence": {
                    "statistics": {"normalized_file": str(normalized_rel)},
                    "detailed_file_inventory": {
                        "found": True,
                        "imported": False,
                        "original_name": "detail.csv",
                        "size_bytes": 999,
                    },
                },
            }
            arkade_normalized = {
                "source_version": "2.12.3",
                "summary": {"date_of_testing": "26. februar 2025", "number_of_tests_run": 54},
                "tests": [],
            }
            coverage = {
                "summary": {
                    "arkade_errors": 0,
                    "arkade_warnings": 0,
                    "covered_by_arkade": 0,
                    "covered_by_both": 0,
                    "covered_by_dwm": 0,
                    "not_covered_in_run": 0,
                },
                "arkade_control_areas": [],
            }

            with patch("noark5_workflow.external_evidence.depot_arkade5.list_arkade5_imports", return_value=[manifest]), patch(
                "noark5_workflow.external_evidence.depot_arkade5.load_arkade5_import",
                return_value={"normalized": arkade_normalized},
            ), patch(
                "noark5_workflow.external_evidence.depot_arkade5.build_combined_coverage",
                return_value=coverage,
            ):
                result = build_arkade5_depot_evidence(
                    work_operations=work,
                    depot_model={"technical_validation": {"tests": []}},
                )

            self.assertEqual(result["format_version"], 3)
            self.assertEqual(result["pronom_summary"]["statistics_imports"], 1)
            self.assertEqual(result["pronom_summary"]["statistics_rows"], 2)
            self.assertEqual(result["pronom_summary"]["total_files"], 20)
            self.assertEqual(result["pronom_summary"]["unique_format_ids"], 2)
            self.assertEqual(result["pronom_summary"]["detailed_inventory_available"], 1)
            self.assertEqual(result["imports"][0]["pronom"]["statistics"]["rows"][1]["format_id"], "fmt/111")

    def test_html_exposes_pronom_statistics_but_not_file_inventory_rows(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.html"
            path.write_text("<html><body><h1>Rapport</h1></body></html>", encoding="utf-8")
            model = {
                "external_validation": {
                    "arkade5": {
                        "summary": {"imports": 1, "covered_by_arkade": 0},
                        "occurrences": {},
                        "pronom_summary": {
                            "statistics_imports": 1,
                            "statistics_rows": 1,
                            "total_files": 12,
                            "unique_format_ids": 1,
                        },
                        "imports": [{
                            "import_id": "import-1",
                            "source_version": "2.12.3",
                            "coverage": {"summary": {}},
                            "pronom": {
                                "available": True,
                                "identification_engine": "Siegfried / PRONOM",
                                "statistics": {
                                    "row_count": 1,
                                    "total_files": 12,
                                    "unique_format_ids": 1,
                                    "unidentified_files": 0,
                                    "rows": [{
                                        "format_id": "fmt/18",
                                        "file_type": "PDF",
                                        "format_version": "1.4",
                                        "raf_220301": "Ja",
                                        "count": 12,
                                    }],
                                },
                                "detailed_file_inventory": {
                                    "found": True,
                                    "imported": False,
                                    "original_name": "detail.csv",
                                    "size_bytes": 999,
                                },
                            },
                        }],
                    }
                }
            }
            inject_arkade5_html(path, model)
            html = path.read_text(encoding="utf-8")
            self.assertIn("Filformater / PRONOM", html)
            self.assertIn("fmt/18", html)
            self.assertIn("detail.csv", html)
            self.assertIn("men ikke importert", html)


if __name__ == "__main__":
    unittest.main()
