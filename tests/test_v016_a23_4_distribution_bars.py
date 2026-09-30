from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_4.py"


class A234DistributionBarsTests(unittest.TestCase):
    def test_runtime_activates_a234(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a23_4 import run_gui", source)

    def test_distribution_bars_are_visually_substantial(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("height=24", source)
        self.assertIn("height=18", source)
        self.assertIn("bar_box", source)
        self.assertIn("pady=7", source)


if __name__ == "__main__":
    unittest.main()
