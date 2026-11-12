"""Release v0.1.11: physical version, packaging, history and compatibility."""
from __future__ import annotations

from pathlib import Path
import re
import tomllib
import unittest

from version import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parents[1]


class V0111ReleaseVersionTests(unittest.TestCase):
    def test_final_release_version_not_alpha(self):
        self.assertEqual(APP_NAME, 'Data Workflow Manager')
        match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.(\d+))*)?', VERSION)
        self.assertIsNotNone(match, VERSION)
        release = tuple(int(match.group(i)) for i in (1, 2, 3))
        self.assertGreaterEqual(release, (0, 1, 11))
        if release == (0, 1, 11):
            self.assertEqual(VERSION, '0.1.11', 'Release v0.1.11 skal ikke ha alpha-suffiks')

    def test_physical_version_file_contains_only_the_release(self):
        # Do not use Path.read_text(): the historical alpha test harness may
        # add in-memory test-only markers. Inspect the actual production file.
        with (ROOT / 'version.py').open('r', encoding='utf-8') as stream:
            source = stream.read()
        self.assertEqual(source, f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n')
        if VERSION.startswith('0.1.11'):
            self.assertNotIn('-a', source)

    def test_distribution_metadata_is_synchronized(self):
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            project = tomllib.load(stream)['project']
        self.assertEqual(project['name'], 'noark5-workflow-manager')
        self.assertEqual(project['version'], VERSION.replace('-a', 'a'))

    def test_release_history_is_complete_and_ordered(self):
        history = (ROOT / 'docs' / 'RELEASES.md').read_text(encoding='utf-8')
        self.assertEqual(history.count('## v0.1.11\n'), 1)
        self.assertLess(history.index('## v0.1.11\n'), history.index('## v0.1.10\n'))
        section = history.split('## v0.1.11\n', 1)[1].split('## v0.1.10\n', 1)[0]
        for phrase in (
            'Enkel modus', 'fire uavhengige kontrollvalg', 'Siegfried',
            'Arkade 5 CLI', 'PRONOM', 'Nasjonalarkivets',
            'Kj\u00f8redetaljer', 'Work', 'Setup',
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.casefold(), section.casefold())
        self.assertIn('depotgodkjenning', section)

    def test_readme_is_general_not_an_alpha_test_log(self):
        content = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('fire uavhengige kontrollvalg', content)
        self.assertIn('Siegfried', content)
        self.assertNotIn('## Enkel start (fra v0.1.11-a1)', content)
        self.assertNotIn('v0.1.11-a3.7', content)

    def test_release_retains_basic_and_external_tool_implementations(self):
        paths = (
            'app/basic_start_v0111_a1.py',
            'gui_qt/basic_main_v0111_a1.py',
            'app/siegfried_tool_v0111_a3.py',
            'noark5_workflow/operations/run_siegfried_pronom.py',
            'gui_qt/result_center_siegfried_v0111_a3.py',
            'gui_qt/setup_format_v0111_a2.py',
            'config/formats/nasjonalarkivet_2026-11-10.json',
        )
        for relative in paths:
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_prior_release_is_still_present(self):
        self.assertTrue((ROOT / 'tests' / 'test_v0110_release_version.py').is_file())
        self.assertTrue((ROOT / 'docs' / 'RELEASE-VERSION-TEST-RULE.md').is_file())


if __name__ == '__main__':
    unittest.main()
