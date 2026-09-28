from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A167LayoutTests(unittest.TestCase):
    def test_runtime_is_wired(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a16_7 import run_gui", main)

    def test_pronom_columns_are_adjacent(self):
        src = (ROOT / "gui" / "depot_result_center_a16_7.py").read_text(encoding="utf-8")
        self.assertIn("mins = (125, 520, 150, 145, 100)", src)
        self.assertIn("height=66", src)


if __name__ == "__main__":
    unittest.main()
