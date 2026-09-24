from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V015A6ArkadeCombinedGuiTests(unittest.TestCase):
    def test_combined_coverage_dialog_is_exposed(self):
        text = (ROOT / "gui" / "depot_result_views_a16.py").read_text(encoding="utf-8")
        self.assertIn("class Arkade5CombinedCoverageDialog", text)
        self.assertIn("Samlet DWM/Arkade-dekning...", text)
        self.assertIn("covered_by_arkade", text)
        self.assertIn("arkade_control_areas", text)

    def test_a6_does_not_promote_arkade_to_dwm_master(self):
        text = (ROOT / "gui" / "depot_result_views_a16.py").read_text(encoding="utf-8")
        self.assertIn("ikke gjort om til DWM-masterresultater", text)
        self.assertIn("automatisk depotkonklusjon", text)

    def test_active_gui_routes_to_a16_result_views(self):
        direct = (ROOT / "gui" / "direct_depot_assessment_dialog_a16.py").read_text(encoding="utf-8")
        overview = (ROOT / "gui" / "noark5_control_overview_dialog_a16.py").read_text(encoding="utf-8")
        app = (ROOT / "gui" / "persistent_app_a48.py").read_text(encoding="utf-8")
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("DepotResultViewsDialogA16", direct)
        self.assertIn("DirectDepotAssessmentDialogA16", overview)
        self.assertIn("Noark5ControlOverviewDialogA16", app)
        self.assertIn("persistent_app_a48 import run_gui", main)

    def test_version_has_not_regressed_before_a6(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.\d+)*)?"', version)
        self.assertIsNotNone(match, "Expected v0.1.5 or newer release/alpha version")
        release = tuple(map(int, match.group(1, 2, 3)))
        self.assertGreaterEqual(release, (0, 1, 5))
        if release == (0, 1, 5) and match.group(4) is not None:
            self.assertGreaterEqual(int(match.group(4)), 6)


if __name__ == "__main__":
    unittest.main()
