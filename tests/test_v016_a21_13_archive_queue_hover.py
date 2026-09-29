from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A2113ArchiveQueueHoverTests(unittest.TestCase):
    def test_runtime_activates_a2113(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a21_13 import run_gui", source)

    def test_hover_shows_full_title_only_when_shortened(self):
        source = (ROOT / "gui" / "depot_result_center_a21_13.py").read_text(encoding="utf-8")
        self.assertIn('if raw_title.strip() != shown_title.strip():', source)
        self.assertIn('"<Enter>"', source)
        self.assertIn('"<Leave>"', source)
        self.assertIn('text=raw_title', source)

    def test_queue_layout_is_unchanged(self):
        source = (ROOT / "gui" / "depot_result_center_a21_13.py").read_text(encoding="utf-8")
        self.assertIn('height=72', source)
        self.assertIn('anchor="center"', source)
        self.assertIn('period_line = f"({period})"', source)
        self.assertIn('status = "Komplett data"', source)


if __name__ == "__main__":
    unittest.main()
