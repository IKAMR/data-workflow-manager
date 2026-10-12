"""Ensure XSD continuation is installed at every workflow dispatch, not only at GUI startup."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui/persistent_app_a4_6_runtime.py'


class XsdWorkflowDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        cls.app = next(node for node in cls.tree.body if isinstance(node, ast.ClassDef) and node.name == 'WorkflowApp')

    def test_startup_and_each_job_execution_restore_a39(self):
        methods = {n.name: n for n in self.app.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertIn('__init__', methods)
        self.assertIn('_execute_job', methods)
        for name in ('__init__', '_execute_job'):
            calls = [n for n in ast.walk(methods[name]) if isinstance(n, ast.Call)]
            self.assertTrue(any(isinstance(c.func, ast.Attribute) and c.func.attr == '_a152_restore_xsd_continuation' for c in calls), name)
        self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == '_execute_job' for n in ast.walk(methods['_execute_job'])))

    def test_xsd_validation_remains_a_finding_not_a_success(self):
        source = (ROOT / 'noark5_workflow/core/job_runner_a39.py').read_text(encoding='utf-8')
        self.assertIn('job.mark_operation_completed(failed_index)', source)
        self.assertIn('outcome.ok', source)
        self.assertIn('not xsd_finding_seen', source)

if __name__ == '__main__':
    unittest.main()
