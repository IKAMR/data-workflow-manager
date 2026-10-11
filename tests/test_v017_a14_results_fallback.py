"""Regression guard: no report must not fall back to Depotvurdering."""
import ast
from pathlib import Path
import unittest


class ResultatvisningerFallbackTests(unittest.TestCase):
    def test_no_old_depot_fallback(self):
        source = (Path(__file__).parents[1] / 'gui' / 'persistent_app_a4_6_runtime.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'WorkflowApp')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_open_depot_assessment')
        branches = [n for n in ast.walk(method) if isinstance(n, ast.If)]
        self.assertTrue(any('report_path is None' in ast.unparse(n.test) for n in branches))
        self.assertNotIn('return super()._open_depot_assessment()\n        if', ast.unparse(method))
        self.assertIn('messagebox.showinfo', source)


if __name__ == '__main__':
    unittest.main()
