from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.external_evidence.arkade5_report import write_arkade5_analysis_reports


class A15ReportExportTests(unittest.TestCase):
    def test_writes_html_and_json_to_selected_output(self):
        analysis = {
            "source_version": "2.13.0",
            "source": {"file": "arkade.json", "sha256": "abc"},
            "source_summary": {"date_of_testing": "2026-02-26"},
            "summary": {"tests": 1, "error": 1, "warning": 0, "review": 0, "ok": 0, "needs_attention": 1},
            "principle": "Ikke automatisk depotkonklusjon.",
            "items": [{
                "test_id": "N5.15",
                "test_name": "Status",
                "attention_level": "error",
                "arkade_status": "error",
                "number_of_errors": 1,
                "explanation": "Arkade registrerte feil.",
                "coverage_classification": "candidate",
                "dwm_candidates": [{"dwm_test_id": "kdrs.c13", "legacy_job_id": "C13"}],
                "reconciliation": None,
                "findings": [{"type": "Error", "message": "Fant feil", "file": "arkivstruktur.xml"}],
            }],
        }
        with tempfile.TemporaryDirectory() as td:
            paths = write_arkade5_analysis_reports(
                analysis, import_id="20260226-abc", output_dir=td
            )
            self.assertEqual(len(paths), 2)
            html_path = next(p for p in paths if p.suffix == ".html")
            json_path = next(p for p in paths if p.suffix == ".json")
            self.assertTrue(html_path.is_file())
            self.assertTrue(json_path.is_file())
            self.assertIn("Arkade 5 – rapportanalyse", html_path.read_text(encoding="utf-8"))
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["source_import_id"], "20260226-abc")

    def test_runtime_activates_a47(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn(
            "from gui.persistent_app_a47 import run_gui",
            (root / "main.py").read_text(encoding="utf-8"),
        )

    def test_gui_has_single_and_batch_report_export(self):
        root = Path(__file__).resolve().parents[1]
        single = (root / "gui" / "arkade5_analysis_dialog_a15.py").read_text(encoding="utf-8")
        batch = (root / "gui" / "depot_result_views_a15.py").read_text(encoding="utf-8")
        self.assertIn("Generer rapport...", single)
        self.assertIn("Generer alle rapporter...", batch)
        self.assertIn("last_report_output_dir", single)


if __name__ == "__main__":
    unittest.main()
