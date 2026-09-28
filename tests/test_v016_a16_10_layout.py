from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A1610LayoutTests(unittest.TestCase):
    def test_runtime_selected(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a16_10 import run_gui", text)

    def test_annual_tab_and_pronom_sort(self):
        text = (ROOT / "gui" / "depot_result_center_a16_10.py").read_text(encoding="utf-8")
        self.assertIn('tabs.add("Per år")', text)
        self.assertIn('self._a1610_pronom_sort = ("count", True)', text)
        self.assertIn("command=lambda k=key: self._sort_pronom(k)", text)


if __name__ == "__main__":
    unittest.main()
