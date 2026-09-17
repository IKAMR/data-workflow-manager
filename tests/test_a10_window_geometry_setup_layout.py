from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class A10WindowGeometrySetupLayoutTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "gui" / "settings_dialog_a10.py").read_text(encoding="utf-8")

    def test_window_options_are_inside_scrollable_setup_body(self):
        self.assertIn("_find_scrollable_frame(self)", self.text)
        self.assertIn('text="Vindu"', self.text)
        self.assertIn("Start med samme vindusposisjon", self.text)
        self.assertIn("Start med samme vindusstørrelse", self.text)

    def test_scrollable_body_lookup_is_recursive(self):
        self.assertIn("def _find_scrollable_frame(widget)", self.text)
        self.assertIn("for child in widget.winfo_children()", self.text)
        self.assertIn("_find_scrollable_frame(child)", self.text)

    def test_window_section_is_appended_after_existing_rows(self):
        self.assertIn("def _next_free_row(frame)", self.text)
        self.assertIn("max_row + 1", self.text)
        self.assertIn("row = _next_free_row(body)", self.text)

    def test_existing_setup_controls_are_never_regridded(self):
        self.assertNotIn("grid_configure(row=", self.text)
        self.assertNotIn("row + 4", self.text)
        self.assertNotIn("tools.grid_configure", self.text)
        self.assertNotIn("buttons.grid_configure", self.text)

    def test_independent_settings_are_still_collected(self):
        self.assertIn('"restore_main_window_position"', self.text)
        self.assertIn('"restore_main_window_size"', self.text)


if __name__ == "__main__":
    unittest.main()
