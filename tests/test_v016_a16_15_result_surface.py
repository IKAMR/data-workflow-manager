from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class A1615ResultSurfaceTests(unittest.TestCase):
    def test_main_uses_a16_15_before_main_guard(self):
        text=(ROOT/'main.py').read_text(encoding='utf-8')
        self.assertLess(text.rfind('from gui.persistent_app_a16_15 import run_gui'), text.rfind('if __name__ == "__main__":'))

    def test_hidden_sink_place_does_not_pass_size(self):
        text=(ROOT/'gui'/'depot_result_center_a16_15.py').read_text(encoding='utf-8')
        self.assertIn('sink = ctk.CTkTextbox(tab, width=1, height=1)', text)
        self.assertIn('sink.place(x=-10000, y=-10000)', text)
        self.assertNotIn('sink.place(x=-10000, y=-10000, width=1, height=1)', text)

if __name__ == '__main__':
    unittest.main()
