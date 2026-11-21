"""Final v0.2.2 release boundary; no Qt or external archives are required."""
from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

from version import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parents[1]


class V022ReleaseTests(unittest.TestCase):
    def test_release_version_matches_distribution(self):
        self.assertEqual(APP_NAME, 'Data Workflow Manager')
        base = tuple(map(int, VERSION.split('-', 1)[0].split('.')))
        self.assertGreaterEqual(base, (0, 2, 2))
        if base == (0, 2, 2):
            self.assertEqual(VERSION, '0.2.2')
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            project = tomllib.load(stream)['project']
        self.assertEqual(project['name'], 'noark5-workflow-manager')
        self.assertEqual(project['version'], VERSION.replace('-a', 'a'))

    def test_exact_physical_version(self):
        self.assertEqual((ROOT / 'version.py').read_text(encoding='utf-8'),
                         f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n')

    def test_a9_version_guard_promoted_to_release(self):
        text = (ROOT / 'tests/test_v022_a9_run_profiles.py').read_text(encoding='utf-8')
        self.assertIn('assert_release_at_least(', text)
        self.assertNotIn("self.assertEqual(VERSION, '0.2.2-a12')", text)

    def test_release_notes_cover_scope_and_known_limits(self):
        text = (ROOT / 'docs/RELEASE-v0.2.2.md').read_text(encoding='utf-8').casefold()
        for marker in ('uavhengige noark 5-uttrekk', '17 av 17',
                       'a100', 'a200', 'a260', 'arkade', 'evidens',
                       'ks-', 'utkast', 'sha-256', 'test.bat', 'workshop',
                       'ikke', '0.2.2-a12'):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_workshop_gui_entrypoints_retained(self):
        # In the full repository these are the existing final a12 components.
        for path in ('app/ks_workshop_v022_a12.py',
                     'gui_qt/ks_workshop_v022_a12.py',
                     'gui_qt/main_v022_a12.py'):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file(), path)


if __name__ == '__main__':
    unittest.main()
