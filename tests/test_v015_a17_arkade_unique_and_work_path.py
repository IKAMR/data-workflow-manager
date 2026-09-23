
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noark5_workflow.external_evidence.depot_arkade5 import (
    add_arkade5_review_points,
    build_arkade5_depot_evidence,
)


class V015A17ArkadeAndWorkPathTests(unittest.TestCase):
    def test_multiple_imports_use_unique_summary_and_occurrence_totals(self):
        manifests = [
            {"import_id": "one", "source": {"original_name": "one.json"}},
            {"import_id": "two", "source": {"original_name": "two.json"}},
        ]

        normalized = {
            "tests": [
                {
                    "test_id": "N5.30",
                    "source_status": "error",
                    "number_of_errors": 1,
                    "results": [],
                }
            ],
            "summary": {},
        }
        model = {"technical_validation": {"tests": []}}

        fake_coverage = {
            "summary": {
                "covered_by_arkade": 1,
                "covered_by_both": 0,
                "covered_by_dwm": 0,
                "not_covered_in_run": 0,
                "arkade_errors": 1,
                "arkade_warnings": 0,
            },
            "arkade_control_areas": [{
                "control_id": "arkade:N5.30",
                "combined_status": "covered_by_arkade",
                "arkade": {"status": "error"},
            }],
        }

        with patch(
            "noark5_workflow.external_evidence.depot_arkade5.list_arkade5_imports",
            return_value=manifests,
        ), patch(
            "noark5_workflow.external_evidence.depot_arkade5.load_arkade5_import",
            return_value={"normalized": normalized},
        ), patch(
            "noark5_workflow.external_evidence.depot_arkade5.build_combined_coverage",
            return_value=fake_coverage,
        ):
            result = build_arkade5_depot_evidence(
                work_operations="x",
                depot_model=model,
            )

        self.assertEqual(result["summary"]["imports"], 2)
        self.assertEqual(result["summary"]["covered_by_arkade"], 1)
        self.assertEqual(result["summary"]["arkade_errors"], 1)
        self.assertEqual(result["occurrences"]["covered_by_arkade"], 2)
        self.assertEqual(result["occurrences"]["arkade_errors"], 2)

    def test_review_text_distinguishes_unique_from_occurrences(self):
        model = {"technical_validation": {"status": "ok"}, "deviations": []}
        external = {
            "summary": {
                "imports": 4,
                "arkade_errors": 5,
                "arkade_warnings": 0,
                "covered_by_arkade": 15,
            },
            "occurrences": {
                "arkade_errors": 12,
                "covered_by_arkade": 60,
            },
        }
        add_arkade5_review_points(model, external)
        text = "\n".join(row["summary"] for row in model["deviations"])
        self.assertIn("5 unike kontrollområder med feil", text)
        self.assertIn("12 feilforekomster", text)
        self.assertIn("15 unike kontrollområder", text)
        self.assertIn("60 ganger", text)

    def test_main_activates_a52_runtime(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a52 import run_gui", text)

    def test_a52_exposes_effective_work_path_in_status_bar(self):
        root = Path(__file__).resolve().parents[1]
        app = (root / "gui" / "persistent_app_a52.py").read_text(encoding="utf-8")
        status = (root / "gui" / "status_bar.py").read_text(encoding="utf-8")
        self.assertIn("_effective_work_operations", app)
        self.assertIn("set_work_operations", app)
        self.assertIn("Arbeid:", status)


if __name__ == "__main__":
    unittest.main()
