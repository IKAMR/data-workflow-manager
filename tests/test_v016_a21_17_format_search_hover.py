from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A2117FormatSearchHoverTests(unittest.TestCase):
    def test_runtime_activates_a2117(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a21_17 import run_gui", source)

    def test_search_is_placed_beside_title(self):
        source = (ROOT / "gui" / "depot_result_center_a21_17.py").read_text(encoding="utf-8")
        self.assertIn('search.place(x=215, y=14, anchor="nw")', source)
        self.assertNotIn('relx=1.0, x=-22', source)

    def test_format_tooltip_is_wide_and_pointer_relative(self):
        source = (ROOT / "gui" / "depot_result_center_a21_17.py").read_text(encoding="utf-8")
        self.assertIn("wraplength=1100", source)
        self.assertIn("event.x_root", source)
        self.assertIn("_a2117_show_format_tooltip", source)


if __name__ == "__main__":
    unittest.main()
