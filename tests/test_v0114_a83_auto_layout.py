"""Regression: auto-fit must not fill widescreen or overflow lower tree."""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'gui_qt' / 'standard_values_v0114_a2.py'

class AutoLayoutContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding='utf-8')
        cls.nodes = ast.parse(cls.source)

    def method(self, name):
        methods = [n for n in ast.walk(self.nodes) if isinstance(n, ast.FunctionDef) and n.name == name]
        self.assertEqual(len(methods), 1)
        return ast.get_source_segment(self.source, methods[0])

    def test_restrained_width_in_ctor_and_auto_fit(self):
        self.assertIn('int(area.width() * .76)', self.source)
        self.assertIn('1500', self.method('_auto_layout'))
        self.assertNotIn('area.width() * .93', self.source)

    def test_fit_based_on_viewport_without_synthetic_minimums(self):
        code = self.method('_fit_columns')
        self.assertIn('self.structure.viewport().width() - 8', code)
        self.assertIn('tree_width - tree_first', code)
        self.assertNotIn('max(350,', code)
        self.assertNotIn('max(760,', code)

    def test_auto_button_and_search_both_fit(self):
        self.assertIn('self.auto_layout_button.clicked.connect(self._auto_layout)', self.source)
        self.assertIn('QTimer.singleShot(0, self._auto_layout)', self.source)

    def test_manual_resizing_does_not_re_auto_fit(self):
        self.assertNotIn('resizeEvent(self', self.source[self.source.index('class XmlOccurrencesDialog'):])
        self.assertNotIn('splitterMoved.connect(self._auto_layout)', self.source)

if __name__ == '__main__':
    unittest.main()
