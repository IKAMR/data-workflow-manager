"""Static integration smoke: a15 must reuse original Qt buttons and timer."""
from __future__ import annotations

from pathlib import Path
import ast
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A15QtIntegrationTests(unittest.TestCase):
    def test_edited_dialog_integrates_derived_refresh_and_warning_review(self):
        source = (ROOT / 'gui_qt/additional_subjobs_v027_a14.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('execute_aftercare(', source)
        self.assertIn('inspect_additional_subjob(', source)
        self.assertIn('approved_warnings=approvals', source)
        self.assertIn('install_compact_simple_run(window)', source)
        self.assertIn('subjob_run_button', source)
        self.assertIn('subjob_run_action', source)
        self.assertIn('window._a9_run_selected_subjob = open_aftercare_for_selection', source)

    def test_compact_layout_moves_existing_qt_controls(self):
        source = (ROOT / 'gui_qt/basic_run_compact_v027_a15.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('basic_option_checks', source)
        self.assertIn('a10_basic_all_button', source)
        self.assertIn('v025_a3_basic_button', source)
        self.assertIn('a14_basic_button', source)
        self.assertIn("timer.timeout.connect", source)
        self.assertIn('QBoxLayout.Direction.TopToBottom', source)

    def test_version_and_distribution_match(self):
        # Verify the release-series floor and metadata without locking to an
        # alpha number; this must also pass after promotion to the final release.
        from version import VERSION
        self.assertRegex(VERSION, r'^\d+\.\d+\.\d+(?:-a\d+)?$')
        release = tuple(int(piece) for piece in VERSION.split('-a', 1)[0].split('.'))
        self.assertGreaterEqual(release, (0, 2, 7))
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            package_version = tomllib.load(stream)['project']['version']
        self.assertEqual(package_version, VERSION.replace('-a', 'a'))


if __name__ == '__main__':
    unittest.main()
