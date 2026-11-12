"""Regression checks for the v0.1.12 shared Setup external-tools hotfix."""
from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SetupSaveRegressionTests(unittest.TestCase):
    def test_external_tool_keys_allowed_by_actual_save_handler(self):
        source = (ROOT / 'app/workbench_api_v0110_a1.py').read_text('utf-8')
        module = ast.parse(source)
        cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'DwmWorkbenchAPI')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'save_setup')
        allowed_assign = next(n for n in ast.walk(method)
                              if isinstance(n, ast.Assign)
                              and any(isinstance(t, ast.Name) and t.id == 'allowed' for t in n.targets))
        allowed = ast.literal_eval(allowed_assign.value)
        gui_source = (ROOT / 'gui_qt/setup_format_v0111_a2.py').read_text('utf-8')
        base_source = (ROOT / 'gui_qt/setup_v018_a7.py').read_text('utf-8')
        self.assertIn('sf_executable', allowed)
        self.assertIn('arkade5_cli_path', allowed)
        self.assertIn("updates['sf_executable']", gui_source)
        self.assertIn('"arkade5_cli_path": self.cli_path.text().strip()', base_source)

    def test_release_version_matches_package(self):
        from version import VERSION
        match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.(\d+))*)?', VERSION)
        self.assertIsNotNone(match, VERSION)
        self.assertGreaterEqual(tuple(map(int, match.group(1, 2, 3))), (0, 1, 12))
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            package_version = tomllib.load(stream)['project']['version']
        self.assertEqual(package_version, VERSION.replace('-a', 'a'))


if __name__ == '__main__':
    unittest.main()
