import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
PANEL = (ROOT / "gui" / "workflow_panel.py").read_text(encoding="utf-8")

class A147TooltipEdgePositionTests(unittest.TestCase):
    def test_tooltip_has_more_pointer_distance(self):
        self.assertIn("OFFSET_X = 22", PANEL)
        self.assertIn("OFFSET_Y = 24", PANEL)

    def test_tooltip_flips_left_near_right_edge(self):
        self.assertIn("pointer_x - width - self.OFFSET_X", PANEL)

    def test_tooltip_flips_above_near_bottom_edge(self):
        self.assertIn("pointer_y - height - self.OFFSET_Y", PANEL)

    def test_tooltip_clamps_to_parent_window(self):
        self.assertIn("parent = self.owner.winfo_toplevel()", PANEL)
        self.assertIn("right - width - margin", PANEL)
        self.assertIn("bottom - height - margin", PANEL)

if __name__ == "__main__":
    unittest.main()
