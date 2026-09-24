
from __future__ import annotations

import unittest
from pathlib import Path


class V015A25ResultSimplificationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def test_result_view_has_three_primary_arkade_entries(self):
        text = (self.root / "gui" / "depot_result_views_a20.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Samlet oversikt...", text)
        self.assertIn("Arkade-kjøringer...", text)
        self.assertIn("Avansert...", text)

    def test_old_all_reports_label_is_not_exposed_as_all_results(self):
        text = (self.root / "gui" / "depot_result_views_a20.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Generer Arkade-analyser...", text)
        self.assertNotIn('("Generer alle rapporter..."', text)

    def test_coverage_dialog_uses_current_relation_model(self):
        text = (self.root / "gui" / "depot_result_views_a20.py").read_text(
            encoding="utf-8"
        )
        for key in ("equivalent", "partial", "complementary", "arkade_only", "unmapped"):
            self.assertIn(key, text)

    def test_old_imports_are_enriched_from_normalized_evidence(self):
        text = (self.root / "gui" / "arkade5_metadata_a25.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('normalized.get("source_version")', text)
        self.assertIn("report_timestamp_from_filename", text)
        self.assertIn("ikke oppgitt", text)

    def test_runtime_activates_a25_result_view_through_a20_layers(self):
        runtime = (self.root / "gui" / "persistent_app_a60.py").read_text(
            encoding="utf-8"
        )
        direct = (
            self.root / "gui" / "direct_depot_assessment_dialog_a20.py"
        ).read_text(encoding="utf-8")
        generic = (
            self.root / "gui" / "depot_assessment_dialog_a20.py"
        ).read_text(encoding="utf-8")

        self.assertIn("DirectDepotAssessmentDialogA20", runtime)
        self.assertIn("DepotAssessmentDialogA20", runtime)
        self.assertIn("DepotResultViewsDialogA20", direct)
        self.assertIn("DepotResultViewsDialogA20", generic)


if __name__ == "__main__":
    unittest.main()
