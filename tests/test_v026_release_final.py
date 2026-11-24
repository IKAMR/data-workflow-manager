"""Final v0.2.6: version, history and unchanged A230/Qt regression contracts."""
from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

from version import APP_NAME, VERSION
from tests.version_assertions import assert_release_at_least

ROOT = Path(__file__).resolve().parents[1]


class V026ReleaseTests(unittest.TestCase):
    def test_release_version_and_distribution_consistency(self):
        self.assertEqual(APP_NAME, 'Data Workflow Manager')
        assert_release_at_least(self, f'VERSION = "{VERSION}"', '0.2.6', 3)
        if VERSION.split('-', 1)[0] == '0.2.6':
            self.assertEqual(VERSION, '0.2.6')
        self.assertEqual(
            (ROOT / 'version.py').read_text(encoding='utf-8'),
            f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n',
        )
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            project = tomllib.load(stream)['project']
        self.assertEqual(project['name'], 'noark5-workflow-manager')
        self.assertEqual(project['version'], VERSION.replace('-a', 'a'))

    def test_full_history_is_retained_and_release_notes_are_concrete(self):
        history = (ROOT / 'docs/RELEASES.md').read_text(encoding='utf-8')
        self.assertEqual(history.count('## v0.2.6\n'), 1)
        self.assertLess(history.index('## v0.2.6\n'), history.index('## v0.2.5\n'))
        previous = ('0.2.5', '0.2.4', '0.2.3', '0.2.2', '0.2.1', '0.2.0',
                    '0.1.15', '0.1.14', '0.1.0')
        for version in previous:
            with self.subTest(version=version):
                self.assertEqual(history.count(f'## v{version}\n'), 1)
        notes = (ROOT / 'docs/RELEASE-v0.2.6.md').read_text(encoding='utf-8')
        for marker in ('siden **v0.2.5**', 'A160', 'A210', 'A220', 'A230',
                       'Filformatvurdering', 'Evidensdekning', 'Work',
                       'docs_layout.py', 'release_gate.py', 'test.bat'):
            with self.subTest(marker=marker):
                self.assertIn(marker.casefold(), notes.casefold())

    def test_a230_and_qt_regressions_remain_active(self):
        for rel in (
            'noark5_workflow/operations/canonical_evidence_v026_a3.py',
            'noark5_workflow/operations/canonical_evidence_v022_a7.py',
            'gui_qt/format_assessment_layout_v026_a2.py',
            'tests/test_v026_a2_format_setup_layout.py',
            'tests/test_v026_a3_a230_evidence.py',
            'tests/test_docs_layout.py',
            'tests/test_release_prepare.py',
        ):
            with self.subTest(file=rel):
                self.assertTrue((ROOT / rel).is_file(), rel)
        profile = (ROOT / 'noark5_workflow/profile.py').read_text(encoding='utf-8')
        self.assertIn('canonical_evidence_v026_a3', profile)
        entrypoint = (ROOT / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        self.assertIn('install_format_assessment_layout()', entrypoint)
        self.assertIn('raise SystemExit(main())', entrypoint)

    def test_a230_documentation_is_not_a_new_alpha_note(self):
        self.assertFalse((ROOT / 'docs/V026-A3-A230-EVIDENSDEKNING.md').exists())
        path = ROOT / 'docs/workflow/EVIDENSDEKNING.md'
        self.assertTrue(path.is_file())
        self.assertIn('A230', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
