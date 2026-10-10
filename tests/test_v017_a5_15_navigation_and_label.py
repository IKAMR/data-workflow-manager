from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]

class A515NavigationTests(unittest.TestCase):
    def test_wrap_and_left_side(self):
        s = (ROOT / 'gui/depot_result_center_v017_a1.py').read_text(encoding='utf-8')
        ast.parse(s)
        self.assertIn('target = (index + step) % len(labels)', s)
        self.assertLess(s.index('self._a5_next_part.pack('), s.index('self._a5_part_menu.pack('))
        self.assertIn("len(labels) > 1", s)
    def test_entry_button_consistent(self):
        s = (ROOT / 'gui/persistent_app_a4_6_runtime.py').read_text(encoding='utf-8')
        ast.parse(s)
        self.assertIn('depot.configure(text="Resultatvisninger"', s)
        self.assertIn('"Depotvurdering"', s)
        self.assertIn('"Råresultater"', s)
