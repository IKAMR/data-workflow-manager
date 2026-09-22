from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class A12RuntimeContractTests(unittest.TestCase):
    def test_main_activates_a44(self):
        self.assertIn("from gui.persistent_app_a44 import run_gui",
                      (ROOT/"main.py").read_text(encoding="utf-8"))
    def test_gui_exposes_test_coverage(self):
        text=(ROOT/"gui"/"depot_result_views_a12.py").read_text(encoding="utf-8")
        self.assertIn('text="Testdekning..."', text)
        self.assertIn("Direkte sammenlignbar", text)
        self.assertIn("Kandidat", text)
        self.assertIn("Ikke kartlagt", text)

if __name__=="__main__":
    unittest.main()
