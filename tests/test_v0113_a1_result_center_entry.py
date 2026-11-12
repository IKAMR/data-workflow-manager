"""Regression: annual result center uses explicit subclass, not runtime monkeypatch."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AnnualResultEntryTests(unittest.TestCase):
    def test_basic_opens_a1_result_center_directly(self):
        source = (ROOT / 'gui_qt/basic_main_v0113_a1.py').read_text(encoding='utf-8')
        self.assertIn('from .result_center_v0113_a1 import ResultCenterWindow', source)

    def test_bootstrap_remains_crash_safe(self):
        source = (ROOT / 'gui_qt/bootstrap_v0113_a1.py').read_text(encoding='utf-8')
        self.assertNotIn('result_module.ResultCenterWindow =', source)
        self.assertIn('install_basic_order()', source)

    def test_annual_view_is_direct_subclass(self):
        code = (ROOT / 'gui_qt/result_center_v0113_a1.py').read_text(encoding='utf-8')
        tree = ast.parse(code)
        classes = [item for item in tree.body if isinstance(item, ast.ClassDef)]
        self.assertEqual([item.name for item in classes], ['ResultCenterWindow'])
        self.assertEqual(ast.unparse(classes[0].bases[0]), '_StableResultCenter')
        self.assertIn('QTimer.singleShot(0, self._restore_annual_layout)', code)


if __name__ == '__main__':
    unittest.main()
