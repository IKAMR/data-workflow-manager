"""v0.2.5-a1 milestone test: remains valid for newer alphas and final release."""
from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

from version import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parents[1]


class V025A1VersionTests(unittest.TestCase):
    def test_version_files_agree_and_v025_a1_is_included(self):
        self.assertEqual(APP_NAME, 'Data Workflow Manager')
        base, marker, alpha = VERSION.partition('-a')
        series = tuple(int(part) for part in base.split('.'))
        self.assertGreaterEqual(series, (0, 2, 5))
        if series == (0, 2, 5) and marker:
            self.assertGreaterEqual(int(alpha), 1)
        with (ROOT / 'pyproject.toml').open('rb') as source:
            project = tomllib.load(source)['project']
        self.assertEqual(project['version'], VERSION.replace('-a', 'a'))
        self.assertEqual(project['name'], 'noark5-workflow-manager')
        self.assertEqual(
            (ROOT / 'version.py').read_text(encoding='utf-8'),
            f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n',
        )

    def test_a170_and_gui_regressions_remain_wired(self):
        entry = (ROOT / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        self.assertIn('DwmMainWindow = _V025A1Window', entry)
        self.assertIn('install_tool_health_setup()', entry)
        self.assertIn('schedule_tool_check(window, api)', entry)
        for path in (
            'noark5_workflow/analysis/definition_engine.py',
            'gui_qt/main_v025_a1.py',
            'tests/test_v025_a1_a170_large_xml.py',
            'tests/test_v025_a1_running_modes.py',
        ):
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == '__main__':
    unittest.main()
