from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A7ArchivePartQueueTests(unittest.TestCase):

    def test_version_is_a7_or_newer_v016(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.\d+)*"', text)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 7)

    def test_a7_builds_only_on_a6_result_view(self):
        source = (ROOT / "gui" / "depot_result_views_a27.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("DepotResultViewsDialogA26", source)
        self.assertIn("super().__init__(master, **kwargs)", source)

    def test_queue_has_all_missing_complete_filters(self):
        source = (ROOT / "gui" / "depot_result_views_a27.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('FILTER_ALL = "Alle"', source)
        self.assertIn('FILTER_MISSING = "Mangler data"', source)
        self.assertIn('FILTER_COMPLETE = "Komplett"', source)
        self.assertIn("CTkSegmentedButton", source)

    def test_search_and_availability_filter_are_combined(self):
        source = (ROOT / "gui" / "depot_result_views_a27.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("text_match = not needle or needle in searchable", source)
        self.assertIn("filter_match = self._matches_archive_filter(index)", source)
        self.assertIn("match = text_match and filter_match", source)

    def test_reset_clears_search_and_filter(self):
        source = (ROOT / "gui" / "depot_result_views_a27.py").read_text(
            encoding="utf-8"
        )
        clear = source.split("def _clear_archive_filter", 1)[1].split(
            "def _show_archive_part", 1
        )[0]
        self.assertIn('self._archive_search_var.set("")', clear)
        self.assertIn("self._archive_filter_var.set(self.FILTER_ALL)", clear)

    def test_next_missing_is_data_availability_not_acceptance(self):
        source = (ROOT / "gui" / "depot_result_views_a27.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Neste med mangler", source)
        self.assertIn("def _next_archive_part_with_missing_data", source)
        self.assertNotIn("godkjent", source.casefold())
        self.assertNotIn("avvist", source.casefold())

    def test_runtime_activates_a67(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a67 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
