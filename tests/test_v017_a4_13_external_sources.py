"""Guard source-neutral tab naming and KDRS detail opening."""
import ast
import unittest
from pathlib import Path


class TestExternalSources(unittest.TestCase):
    def test_generic_tab_and_existing_detail(self):
        source = (Path(__file__).resolve().parents[1] / 'gui' / 'depot_result_center_v017_a1.py').read_text(encoding='utf-8')
        self.assertIn('tabs.add("Eksterne kilder")', source)
        self.assertIn('tabs.tab("Eksterne kilder")', source)
        self.assertNotIn('tabs.add("KDRS Query")', source)
        self.assertIn('infer_work_operations_from_depot_report(self.report_path)', source)
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'KdrsQueryResultsDialog']
        self.assertTrue(any(
            any(k.arg == 'work_operations' and isinstance(k.value, ast.Name) and k.value.id == 'work'
                for k in call.keywords)
            and any(k.arg == 'report_path' and isinstance(k.value, ast.Attribute)
                    and isinstance(k.value.value, ast.Name) and k.value.value.id == 'self'
                    and k.value.attr == 'report_path' for k in call.keywords)
            for call in calls
        ), 'KDRS-dialogen skal få både jobbarbeidsmappe og depotrapportsti')


if __name__ == '__main__':
    unittest.main()
