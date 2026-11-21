"""v0.2.4 release boundary: real files, alpha promotion and preserved history."""
from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

from version import APP_NAME, VERSION
from tests.version_assertions import assert_release_at_least

ROOT = Path(__file__).resolve().parents[1]


class V024ReleaseTests(unittest.TestCase):
    def test_runtime_distribution_and_a5_milestone(self):
        self.assertEqual(APP_NAME, 'Data Workflow Manager')
        assert_release_at_least(self, f'VERSION = "{VERSION}"', '0.2.4', 5)
        # The release itself cannot still have the a5 suffix. This does not
        # require future DWM series to identify themselves as v0.2.4.
        if VERSION.split('-', 1)[0] == '0.2.4':
            self.assertEqual(VERSION, '0.2.4')
        self.assertEqual(
            (ROOT / 'version.py').read_text(encoding='utf-8'),
            f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n',
        )
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            project = tomllib.load(stream)['project']
        self.assertEqual(project['name'], 'noark5-workflow-manager')
        self.assertEqual(project['version'], VERSION.replace('-a', 'a'))

    def test_single_complete_history_entry_and_release_notes(self):
        history = (ROOT / 'docs/RELEASES.md').read_text(encoding='utf-8')
        self.assertEqual(history.count('## v0.2.4\n'), 1)
        self.assertLess(history.index('## v0.2.4\n'), history.index('## v0.2.3\n'))
        for version in ('0.2.3', '0.2.2', '0.2.1', '0.2.0', '0.1.15', '0.1.0'):
            with self.subTest(version=version):
                self.assertIn(f'## v{version}\n', history)
        notes = (ROOT / 'docs/RELEASE-v0.2.4.md').read_text(encoding='utf-8')
        for name in ('siden **v0.2.3**', 'Siegfried', 'Fortsett', 'Nullstill',
                     'Arkade 5', 'Kjøredetaljer', 'PRONOM', 'test.bat',
                     'UTKAST', '0.2.4-a5'):
            with self.subTest(marker=name):
                self.assertIn(name.casefold(), notes.casefold())

    def test_last_alpha_test_is_still_enforced_but_not_alpha_locked(self):
        test_source = (ROOT / 'tests/test_v024_a5_tool_health.py').read_text('utf-8')
        self.assertIn("assert_release_at_least(self, version, '0.2.4', 5)", test_source)
        self.assertNotIn("self.assertIn('VERSION = \"0.2.4-a5\"'", test_source)
        self.assertNotIn("self.assertIn('version = \"0.2.4a5\"'", test_source)
        self.assertIn('PureWindowsPath', test_source)

    def test_previous_release_and_source_code_are_not_displaced(self):
        for item in (
            'docs/RELEASE-v0.2.3.md',
            'gui_qt/main_v024_a4.py',
            'app/workbench_api_v024_a3.py',
            'app/tool_health_v024_a5.py',
            'noark5_workflow/operations/siegfried_resilient_v024_a1.py',
        ):
            with self.subTest(path=item):
                self.assertTrue((ROOT / item).is_file(), item)


if __name__ == '__main__':
    unittest.main()
