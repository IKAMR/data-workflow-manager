"""a1.12: a1.11's column installer must not prevent Qt startup.

The feature module remains installed but inactive. This narrow test is Qt-free;
full Windows GUI startup must still be tested on the operator's machine.
"""
from __future__ import annotations

from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestStartupRecovery(unittest.TestCase):
    def test_main_does_not_import_or_call_a111_columns(self):
        source = (ROOT / 'gui_qt' / '__main__.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertNotIn('workflow_columns_v022_a1_11', source)
        self.assertNotIn('install_editable_workflow_columns', source)

    def test_main_retains_required_installs_and_runtime(self):
        source = (ROOT / 'gui_qt' / '__main__.py').read_text(encoding='utf-8')
        for text in (
            'from gui_qt.basic_multijob_v022_a1_2 import DwmMainWindow',
            'install_file_dialog_navigation_contrast(application)',
            'install_setup_reset_actions()',
            'install_start_navigation(window)',
            'install_integrated_home(window)',
            'install_depot_profile_controls(window)',
            'window.show()',
            'code = application.exec()',
            'return code',
        ):
            with self.subTest(name=text):
                self.assertIn(text, source)

    def test_optional_a111_module_kept_for_future_fix(self):
        # This is not a deletion of the a1.11 change; only its eager startup
        # activation is reverted until a real Windows/Qt traceback is known.
        feature = ROOT / 'gui_qt' / 'workflow_columns_v022_a1_11.py'
        self.assertTrue(feature.is_file())
        ast.parse(feature.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
