import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
PANEL = (ROOT / "gui" / "workflow_panel.py").read_text(encoding="utf-8")

class A148TooltipGeometryTests(unittest.TestCase):
    def test_native_toplevel_avoids_ctk_pre_map_scaling_clip(self):
        self.assertIn("tip = tk.Toplevel(self.owner)", PANEL)

    def test_tooltip_geometry_sets_explicit_size_and_position(self):
        self.assertIn('self.window.geometry(f"{width}x{height}+{x}+{y}")', PANEL)

    def test_tooltip_can_wrap_to_available_application_width(self):
        self.assertIn("wraplength=max(120, available_width - 24)", PANEL)

    def test_tooltip_flips_at_right_and_bottom_edges(self):
        self.assertIn("pointer_x - width - self.OFFSET_X", PANEL)
        self.assertIn("pointer_y - height - self.OFFSET_Y", PANEL)

if __name__ == "__main__":
    unittest.main()
