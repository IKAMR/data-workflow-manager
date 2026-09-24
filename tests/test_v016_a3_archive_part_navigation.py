from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A3ArchivePartNavigationTests(unittest.TestCase):

    def test_version_is_a3_or_newer_v016(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.\d+)*"', version)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 3)

    def test_result_view_adds_archive_part_search_and_status_summary(self):
        source = (ROOT / "gui" / "depot_result_views_a23.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Finn arkivdel", source)
        self.assertIn("systemID eller tittel", source)
        self.assertIn("Teknisk status:", source)
        self.assertIn("Vurderingspunkter:", source)
        self.assertIn("Arkade-kjøringer:", source)
        self.assertIn("_filter_archive_parts", source)

    def test_a3_preserves_a2_archive_part_first_layer(self):
        source = (ROOT / "gui" / "depot_result_views_a23.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("DepotResultViewsDialogA22", source)
        self.assertIn("_PRIMARY_FIELDS", source)
        self.assertIn("_SECONDARY_FIELDS", source)

    def test_runtime_activates_a63(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a63 import run_gui", main)

        runtime = (ROOT / "gui" / "persistent_app_a63.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Noark5ControlOverviewDialogA23", runtime)
        self.assertIn("DirectDepotAssessmentDialogA23", runtime)
        self.assertIn("DepotAssessmentDialogA23", runtime)


if __name__ == "__main__":
    unittest.main()
