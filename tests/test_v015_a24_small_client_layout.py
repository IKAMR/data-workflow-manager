
from __future__ import annotations

import unittest
from pathlib import Path


class V015A24SmallClientLayoutTests(unittest.TestCase):
    def test_runtime_sets_smaller_logical_minimum(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "persistent_app_a59.py").read_text(encoding="utf-8")
        self.assertIn("MIN_WIDTH = 960", text)
        self.assertIn("MIN_HEIGHT = 560", text)
        self.assertIn("self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)", text)

    def test_panels_do_not_force_requested_height(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "persistent_app_a59.py").read_text(encoding="utf-8")
        self.assertIn("self.source_panel.grid_propagate(False)", text)
        self.assertIn("self.workflow_panel.grid_propagate(False)", text)

    def test_source_panel_yields_height_before_fixed_workflow_controls(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "persistent_app_a59.py").read_text(encoding="utf-8")
        self.assertIn("return 150", text)
        self.assertIn("return 180", text)
        self.assertIn("return 220", text)
        self.assertIn("self.source_panel.configure(height=source_height)", text)

    def test_small_width_reduces_left_column(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "persistent_app_a59.py").read_text(encoding="utf-8")
        self.assertIn("left_width = 320", text)
        self.assertIn("left_width = 350", text)
        self.assertIn("left.configure(width=left_width)", text)

    def test_workflow_panel_still_owns_scrollable_operation_area(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "workflow_panel.py").read_text(encoding="utf-8")
        self.assertIn("CTkScrollableFrame", text)


if __name__ == "__main__":
    unittest.main()
