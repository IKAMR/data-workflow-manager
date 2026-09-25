from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A5ArchivePartMaterializationTests(unittest.TestCase):

    def test_version_is_a5_or_newer_v016(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.\d+)*"', text)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 5)

    def test_health_is_data_availability_not_faglig_status(self):
        source = (ROOT / "gui" / "depot_result_views_a25.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def _archive_part_health", source)
        self.assertIn("Dette beskriver datatilgjengelighet, ikke faglig godkjenning.", source)
        self.assertIn("Alle nøkkelfelt materialisert", source)
        self.assertIn("Ingen nøkkelfelt materialisert", source)

    def test_archive_list_shows_available_and_missing_field_counts(self):
        source = (ROOT / "gui" / "depot_result_views_a25.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("nøkkelfelt", source)
        self.assertIn("Mangler {health['missing']}", source)

    def test_previous_next_navigation_is_present(self):
        source = (ROOT / "gui" / "depot_result_views_a25.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("← Forrige", source)
        self.assertIn("Neste →", source)
        self.assertIn("def _previous_archive_part", source)
        self.assertIn("def _next_archive_part", source)

    def test_a5_builds_on_a4_rich_view(self):
        source = (ROOT / "gui" / "depot_result_views_a25.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("DepotResultViewsDialogA24", source)

    def test_a5_waits_until_a4_constructor_has_completed(self):
        source = (ROOT / "gui" / "depot_result_views_a25.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def __init__(self, master, **kwargs)", source)
        self.assertIn("super().__init__(master, **kwargs)", source)
        self.assertIn("self._install_a5_archive_part_controls()", source)
        self.assertIn("assessment = getattr(self, \"_assessment_surface\", None)", source)
        build_block = source.split("def _build_archive_parts_tab", 1)[1].split(
            "def _install_a5_archive_part_controls", 1
        )[0]
        self.assertNotIn("_assessment_surface.grid_configure", build_block)

    def test_runtime_activates_a65(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a65 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
