from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A169LayoutTests(unittest.TestCase):
    def test_runtime_points_to_a169(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a16_9 import run_gui", text)

    def test_a169_has_period_controls_and_pronom_fixes(self):
        text = (ROOT / "gui" / "depot_result_center_a16_9.py").read_text(encoding="utf-8")
        self.assertIn("_place_period_before_years", text)
        self.assertIn("_render_a169_controls", text)
        self.assertIn("_rebuild_pronom_table", text)
        self.assertIn('"Formatversjon"', text)
        self.assertIn('"RAF-220301"', text)
        self.assertIn('"Antall"', text)


if __name__ == "__main__":
    unittest.main()
