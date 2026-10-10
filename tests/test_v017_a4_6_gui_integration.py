from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class A46GuiIntegrationTests(unittest.TestCase):
    def test_active_result_window_contains_external_sources_tab(self):
        source = (ROOT / 'gui/depot_result_center_v017_a1.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        self.assertIn('tabs.add("Eksterne kilder")', source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id == 'KdrsQueryResultsDialog']
        self.assertTrue(calls, 'KDRS Query detail dialog must remain accessible')
        self.assertTrue(any(any(keyword.arg == 'work_operations' for keyword in call.keywords)
                            for call in calls), 'KDRS Query dialog must receive work_operations')
        self.assertIn('infer_work_operations_from_depot_report(self.report_path)', source)

    def test_live_runtime_preserves_current_baseline_and_layers_fix(self):
        entry = (ROOT / 'gui/persistent_app_a27_2.py').read_text(encoding='utf-8')
        ast.parse(entry)
        self.assertIn('from .persistent_app_a4_6_runtime import WorkflowApp as CurrentWorkflowApp', entry)
        self.assertIn('app = CurrentWorkflowApp()', entry)

    def test_buttons_and_splitter(self):
        source = (ROOT / 'gui/persistent_app_a4_6_runtime.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('((1, depot), (2, raw), (3, clear))', source)
        self.assertIn('splitter.configure(border_width=0)', source)
        self.assertIn('widget.grid_remove()', source)

if __name__ == '__main__':
    unittest.main()
