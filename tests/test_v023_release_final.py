"""Final v0.2.3 is a release, not an alpha, and retains all prior history."""
from pathlib import Path
import tomllib
import unittest

from version import APP_NAME, VERSION
from tests.version_assertions import assert_release_at_least

ROOT = Path(__file__).resolve().parents[1]


class V023Release(unittest.TestCase):
    def test_final_runtime_distribution_and_milestone(self):
        self.assertEqual(APP_NAME, 'Data Workflow Manager')
        if VERSION == '0.2.3' or VERSION.startswith('0.2.3-a'):
            self.assertEqual(VERSION, '0.2.3')
        assert_release_at_least(self, f'VERSION = "{VERSION}"', '0.2.3', 19)
        self.assertEqual((ROOT / 'version.py').read_text(encoding='utf-8'),
                         f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n')
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            self.assertEqual(tomllib.load(stream)['project']['version'], VERSION.replace('-a', 'a'))

    def test_history_keeps_all_prior_releases_and_one_new_entry(self):
        history = (ROOT / 'docs/RELEASES.md').read_text(encoding='utf-8')
        self.assertEqual(history.count('## v0.2.3\n'), 1)
        self.assertLess(history.index('## v0.2.3\n'), history.index('## v0.2.2\n'))
        for old in ('## v0.2.2\n', '## v0.2.1\n', '## v0.2.0\n', '## v0.1.15\n', '## v0.1.0\n'):
            self.assertIn(old, history)
        notes = (ROOT / 'docs/RELEASE-v0.2.3.md').read_text(encoding='utf-8')
        self.assertIn('siden **v0.2.2**', notes)
        self.assertIn('UTKAST', notes)


if __name__ == '__main__':
    unittest.main()
