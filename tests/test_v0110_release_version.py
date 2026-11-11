"""Release v0.1.10: physical version, packaging, history and alpha guards."""
from __future__ import annotations

from pathlib import Path
import re
import tomllib
import unittest

from version import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parents[1]


class V0110ReleaseVersionTests(unittest.TestCase):
    def test_final_release_version_not_alpha(self):
        self.assertEqual(APP_NAME, 'Data Workflow Manager')
        match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.(\d+))*)?', VERSION)
        self.assertIsNotNone(match, VERSION)
        release = tuple(int(match.group(i)) for i in (1, 2, 3))
        self.assertGreaterEqual(release, (0, 1, 10))
        if release == (0, 1, 10):
            self.assertEqual(VERSION, '0.1.10', 'Release 0.1.10 skal ikke ha alpha-suffiks')

    def test_physical_version_file_contains_only_the_release(self):
        # Open the actual file: run_tests.py may add synthetic historical
        # alpha markers to Path.read_text() in memory, never to production.
        with (ROOT / 'version.py').open('r', encoding='utf-8') as stream:
            source = stream.read()
        self.assertEqual(source, f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n')
        if VERSION.startswith('0.1.10'):
            self.assertNotIn('-a', source)

    def test_distribution_metadata_is_synchronized(self):
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            project = tomllib.load(stream)['project']
        self.assertEqual(project['name'], 'noark5-workflow-manager')
        self.assertEqual(project['version'], VERSION.replace('-a', 'a'))

    def test_release_history_is_complete_and_ordered(self):
        history = (ROOT / 'docs' / 'RELEASES.md').read_text(encoding='utf-8')
        self.assertEqual(history.count('## v0.1.10\n'), 1)
        self.assertLess(history.index('## v0.1.10\n'), history.index('## v0.1.9\n'))
        section = history.split('## v0.1.10\n', 1)[1].split('## v0.1.9\n', 1)[0]
        for keyword in (
            'Resultatvisninger', 'Arkade 5', 'PRONOM', 'RAF-220301',
            'Lesbar visning', 'Råtekst / JSON', 'Auto størrelse', 'Setup',
            'SHA-256', 'fargetemaer', 'Periodevurdering',
        ):
            with self.subTest(keyword=keyword):
                self.assertIn(keyword, section)
        self.assertIn('brukertesting', section)
        self.assertIn('ikke automatisk', section)

    def test_historical_a2_a3_version_regressions_accept_completed_release(self):
        a2 = (ROOT / 'tests' / 'test_v0110_a2_setup_usability.py').read_text(encoding='utf-8')
        a3 = (ROOT / 'tests' / 'test_v0110_a3_appearance_windows.py').read_text(encoding='utf-8')
        self.assertIn('self.assertGreaterEqual(release, (0, 1, 10))', a2)
        self.assertIn('self.assertGreaterEqual(release, (0, 1, 10))', a3)
        self.assertNotIn("self.assertTrue(VERSION.startswith('0.1.10-a'))", a2)
        self.assertNotIn("self.assertRegex(VERSION, r'^0\\.1\\.10-a[0-9]+$')", a3)

    def test_release_does_not_remove_a5_presentation(self):
        for relative in (
            'app/format_policy_v0110_a4.py',
            'gui_qt/result_center_v0110_a4.py',
            'gui_qt/result_detail_view_v0110_a5.py',
            'config/formats/nasjonalarkivet_2026-11-10.json',
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())


if __name__ == '__main__':
    unittest.main()
