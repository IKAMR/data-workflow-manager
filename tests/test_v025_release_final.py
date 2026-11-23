"""Release v0.2.5: no alpha lock, retained history and Qt start guard."""
from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

from version import APP_NAME, VERSION
from tests.version_assertions import assert_release_at_least

ROOT = Path(__file__).resolve().parents[1]


class V025ReleaseTests(unittest.TestCase):
    def test_final_version_and_distribution(self):
        self.assertEqual(APP_NAME, 'Data Workflow Manager')
        assert_release_at_least(self, f'VERSION = "{VERSION}"', '0.2.5', 3)
        if VERSION.split('-', 1)[0] == '0.2.5':
            self.assertEqual(VERSION, '0.2.5')
        self.assertEqual(
            (ROOT / 'version.py').read_text(encoding='utf-8'),
            f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n',
        )
        with (ROOT / 'pyproject.toml').open('rb') as source:
            project = tomllib.load(source)['project']
        self.assertEqual(project['name'], 'noark5-workflow-manager')
        self.assertEqual(project['version'], VERSION.replace('-a', 'a'))

    def test_history_is_complete_and_chronological(self):
        history = (ROOT / 'docs/RELEASES.md').read_text(encoding='utf-8')
        self.assertEqual(history.count('## v0.2.5\n'), 1)
        self.assertLess(history.index('## v0.2.5\n'), history.index('## v0.2.4\n'))
        for version in ('0.2.4', '0.2.3', '0.2.2', '0.2.1', '0.2.0', '0.1.15', '0.1.14', '0.1.0'):
            with self.subTest(version=version):
                self.assertIn(f'## v{version}\n', history)
        release = (ROOT / 'docs/RELEASE-v0.2.5.md').read_text(encoding='utf-8')
        for marker in ('siden **v0.2.4**', 'A170', 'A120', 'A180',
                       'Fortsett og kj', 'Enkel', 'Avansert', 'start.bat',
                       'test.bat', 'Work', '0.2.5'):
            with self.subTest(marker=marker):
                self.assertIn(marker.casefold(), release.casefold())

    def test_alpha_regressions_and_gui_entrypoint_are_preserved(self):
        for relative in (
            'gui_qt/main_v025_a1.py', 'gui_qt/main_v025_a3.py',
            'app/batch_continue_v025_a3.py',
            'noark5_workflow/analysis/legacy_a170_stream.py',
            'tests/test_v025_a1_a170_large_xml.py',
            'tests/test_v025_a1_running_modes.py',
            'tests/test_v025_a3_remaining_batch.py',
            'tests/test_v025_a3_fix1_start_entrypoint.py',
        ):
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file(), relative)
        entry = (ROOT / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        self.assertIn('DwmMainWindow = _V025A3Window', entry)
        self.assertIn("if __name__ == '__main__':", entry)
        self.assertIn('raise SystemExit(main())', entry)
        test = (ROOT / 'tests/test_v025_a3_release_wiring.py').read_text(encoding='utf-8')
        self.assertIn('assert_release_at_least(', test)


if __name__ == '__main__':
    unittest.main()
