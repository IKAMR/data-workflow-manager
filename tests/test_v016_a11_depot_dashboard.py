from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A11DepotDashboardTests(unittest.TestCase):

    def test_version_is_a11_or_newer(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)', text)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 11)

    def test_dashboard_extends_a10_without_new_analysis(self):
        source = (ROOT / "gui" / "depot_result_views_a31.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("DepotResultViewsDialogA30", source)
        self.assertIn("Datagrunnlag", source)
        self.assertIn("Vurderingspunkter", source)
        self.assertNotIn("run_xpath", source)
        self.assertNotIn("build_depot_report_model", source)

    def test_dashboard_has_extract_level_archive_part_counts(self):
        source = (ROOT / "gui" / "depot_result_views_a31.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('("archive_parts", "Arkivdeler")', source)
        self.assertIn('("complete", "Komplett data")', source)
        self.assertIn('("missing", "Mangler data")', source)
        self.assertIn("def _dashboard_counts", source)

    def test_dashboard_keeps_data_status_separate_from_treatment_status(self):
        source = (ROOT / "gui" / "depot_result_views_a31.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Behandlingsstatus", source)
        self.assertIn('REVIEW_NOT_STARTED = "Ikke vurdert"', source)
        self.assertIn("Dette er ikke det samme som faglig godkjenning.", source)
        self.assertIn("Ingen automatisk godkjenning", source)

    def test_archive_cards_explain_why_attention_is_needed(self):
        source = (ROOT / "gui" / "depot_result_views_a31.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Datagrunnlag: mangler", source)
        self.assertIn("Datagrunnlag: komplett", source)
        self.assertIn("Kontrollgrunnlag som krever oppmerksomhet:", source)

    def test_dashboard_includes_visual_data_distribution(self):
        source = (ROOT / "gui" / "depot_result_views_a31.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("tk.Canvas", source)
        self.assertIn("create_arc", source)
        self.assertIn("Komplett", source)
        self.assertIn("Mangler", source)

    def test_a11_preserves_a10_storage_runtime(self):
        source = (ROOT / "gui" / "persistent_app_a71.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("A70WorkflowApp", source)
        self.assertIn("self._depot_report_for_job(job)", source)
        self.assertIn("storage_unavailable_path=unavailable_path", source)

    def test_all_result_entry_points_route_to_a31(self):
        for filename in (
            "depot_assessment_dialog_a31.py",
            "direct_depot_assessment_dialog_a31.py",
        ):
            source = (ROOT / "gui" / filename).read_text(encoding="utf-8")
            self.assertIn("DepotResultViewsDialogA31", source)

        overview = (
            ROOT / "gui" / "noark5_control_overview_dialog_a31.py"
        ).read_text(encoding="utf-8")
        self.assertIn("DirectDepotAssessmentDialogA31", overview)

    def test_runtime_activates_a71(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a71 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
