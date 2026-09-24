from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V016A2ArchivePartGuiTests(unittest.TestCase):
    def test_archive_part_view_is_primary_review_surface(self):
        source = (ROOT / "gui" / "depot_result_views_a22.py").read_text(encoding="utf-8")
        self.assertIn('tabs.set("Arkivdeler")', source)
        self.assertIn("Arkivdeler – vurderingsoversikt", source)
        self.assertIn("SPORBARHET", source)
        self.assertIn("Kommentarer til arkivdel...", source)

    def test_archive_part_view_preserves_existing_result_model(self):
        source = (ROOT / "gui" / "depot_result_views_a22.py").read_text(encoding="utf-8")
        self.assertIn('self.model.get("archive_parts")', source)
        self.assertNotIn("build_depot_report_model", source)
        self.assertNotIn("run_xpath", source)

    def test_a2_runtime_routes_all_result_entry_points_to_a22(self):
        runtime = (ROOT / "gui" / "persistent_app_a62.py").read_text(encoding="utf-8")
        self.assertIn("Noark5ControlOverviewDialogA22", runtime)
        self.assertIn("DirectDepotAssessmentDialogA22", runtime)
        self.assertIn("DepotAssessmentDialogA22", runtime)
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a62 import run_gui", main)

    def test_version_is_v016_a2_or_newer_in_same_series(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.\d+)*"', version)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 2)


if __name__ == "__main__":
    unittest.main()
