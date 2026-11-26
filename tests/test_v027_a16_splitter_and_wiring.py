"""a16: scoped Advanced history splitter styling and error visibility."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from gui_qt.advanced_splitter_v027_a16 import (
    install_visible_run_history_splitter, splitter_handle_css,
)

ROOT = Path(__file__).resolve().parents[1]


class _FakeSplitter:
    def __init__(self):
        self.name = None
        self.width = None
        self.style = None

    def setObjectName(self, value): self.name = value
    def setHandleWidth(self, value): self.width = value
    def setStyleSheet(self, value): self.style = value


class A16SplitterTests(unittest.TestCase):
    def test_only_vertical_history_splitter_is_styled(self):
        splitter = _FakeSplitter()
        window = type('Window', (), {'run_history_splitter': splitter})()
        self.assertTrue(install_visible_run_history_splitter(window))
        self.assertEqual(splitter.name, 'dwm_a16_run_history_splitter')
        self.assertGreaterEqual(splitter.width, 5)
        self.assertIn('::handle:vertical', splitter.style)
        self.assertIn('::handle:vertical:hover', splitter.style)
        self.assertNotIn('::handle:horizontal', splitter.style)

    def test_missing_splitter_safe(self):
        self.assertFalse(install_visible_run_history_splitter(object()))

    def test_entrypoint_wires_install_after_window_construction(self):
        source = (ROOT / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('install_visible_run_history_splitter(window)', source)
        self.assertLess(source.index('window = DwmMainWindow(api)'),
                        source.index('install_visible_run_history_splitter(window)'))

    def test_regression_operation_has_evidence_retention_and_error_status(self):
        source = (ROOT / 'noark5_workflow/operations/run_noark5_xpath_tests.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('runner-error.txt', source)
        self.assertIn('XPATH MOTORFEIL', source)
        self.assertIn('XPATH REGRESJON', source)
        self.assertIn('self.execution_profile == "regression"', source)
        self.assertIn('return OperationResult(False, message + detail, data=data)', source)

    def test_version_metadata_synced(self):
        import tomllib
        from version import VERSION
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            self.assertEqual(tomllib.load(stream)['project']['version'], VERSION.replace('-a', 'a'))


if __name__ == '__main__':
    unittest.main()
