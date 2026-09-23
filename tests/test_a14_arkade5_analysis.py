from pathlib import Path
import unittest

from noark5_workflow.external_evidence.arkade5_analysis import build_arkade5_analysis


class A14ArkadeAnalysisTests(unittest.TestCase):
    def test_errors_and_non_equivalent_coverage_are_prioritized(self):
        normalized = {
            "source_version": "2.13.0",
            "source": {"file": "report.json", "sha256": "abc"},
            "summary": {"date_of_testing": "2026-02-26"},
            "tests": [
                {"test_id": "N5.32", "test_name": "Arkade only", "source_status": "ok", "number_of_errors": 0, "results": []},
                {"test_id": "N5.04", "test_name": "Arkiv", "source_status": "error", "number_of_errors": 1, "results": [{"result_type": "Error", "message": "Fant feil", "location": {"file_name": "arkivstruktur.xml", "line_numbers": [10]}}]},
            ],
        }
        analysis = build_arkade5_analysis(normalized)
        self.assertEqual(analysis["summary"]["tests"], 2)
        self.assertEqual(analysis["summary"]["error"], 1)
        self.assertEqual(analysis["summary"]["review"], 1)
        self.assertEqual(analysis["items"][0]["test_id"], "N5.04")
        self.assertEqual(analysis["items"][0]["findings"][0]["message"], "Fant feil")
        by_id = {row["test_id"]: row for row in analysis["items"]}
        self.assertEqual(by_id["N5.32"]["coverage_classification"], "arkade_only")

    def test_analysis_is_not_automatic_depot_decision(self):
        analysis = build_arkade5_analysis({"tests": []})
        self.assertIn("ikke en automatisk depotgodkjenning", analysis["principle"])


class A14RuntimeContractTests(unittest.TestCase):
    def test_main_activates_a46(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a46 import run_gui", text)

    def test_gui_exposes_arkade_analysis(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "depot_result_views_a14.py").read_text(encoding="utf-8")
        self.assertIn('text="Analyser Arkade 5..."', text)
        self.assertIn("Arkade5AnalysisSelectionDialog", text)


if __name__ == "__main__":
    unittest.main()
