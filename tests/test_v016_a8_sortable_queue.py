from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A8SortableQueueTests(unittest.TestCase):

    def test_version_is_a8_or_newer_v016(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.\d+)*"', text)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 8)

    def test_a8_builds_on_a7_queue(self):
        source = (ROOT / "gui" / "depot_result_views_a28.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("DepotResultViewsDialogA27", source)
        self.assertIn("super().__init__(master, **kwargs)", source)

    def test_sort_modes_exist(self):
        source = (ROOT / "gui" / "depot_result_views_a28.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('SORT_ORIGINAL = "Original"', source)
        self.assertIn('SORT_MISSING = "Flest mangler"', source)
        self.assertIn('SORT_TITLE = "Tittel"', source)
        self.assertIn("def _sorted_archive_indices", source)

    def test_visible_queue_is_combined_search_filter_and_sort(self):
        source = (ROOT / "gui" / "depot_result_views_a28.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("ordered = self._sorted_archive_indices()", source)
        self.assertIn("text_match = not needle or needle in searchable", source)
        self.assertIn("filter_match = self._matches_archive_filter(index)", source)
        self.assertIn("self._visible_archive_indices = visible", source)

    def test_previous_next_use_visible_queue(self):
        source = (ROOT / "gui" / "depot_result_views_a28.py").read_text(
            encoding="utf-8"
        )
        previous = source.split("def _previous_archive_part", 1)[1].split(
            "def _next_archive_part", 1
        )[0]
        following = source.split("def _next_archive_part", 1)[1].split(
            "def _next_archive_part_with_missing_data", 1
        )[0]
        self.assertIn("_visible_archive_indices", previous)
        self.assertIn("_visible_archive_indices", following)

    def test_next_missing_respects_visible_queue(self):
        source = (ROOT / "gui" / "depot_result_views_a28.py").read_text(
            encoding="utf-8"
        )
        block = source.split(
            "def _next_archive_part_with_missing_data", 1
        )[1].split("def _update_health_strip", 1)[0]
        self.assertIn("_visible_archive_indices", block)
        self.assertNotIn("range(1, total + 1)", block)

    def test_reset_also_restores_original_sort(self):
        source = (ROOT / "gui" / "depot_result_views_a28.py").read_text(
            encoding="utf-8"
        )
        clear = source.split("def _clear_archive_filter", 1)[1].split(
            "def _show_archive_part", 1
        )[0]
        self.assertIn("self._archive_sort_var.set(self.SORT_ORIGINAL)", clear)

    def test_runtime_activates_a68(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a68 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
