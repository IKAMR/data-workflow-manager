"""Regresjonsvern for gruppene i Kjøring i Enkel modus."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'basic_main_v0113_a2.py'


class RunSectionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source)
        window = next(node for node in cls.tree.body if isinstance(node, ast.ClassDef)
                      and node.name == 'DwmMainWindow')
        method = next(node for node in window.body if isinstance(node, ast.FunctionDef)
                      and node.name == '_a3_install_auto_views')
        cls.install_source = ast.get_source_segment(cls.source, method)

    def test_control_and_view_groups_are_separate(self):
        self.assertIn("label.setText('Kontroller som skal kjøres')", self.install_source)
        self.assertIn("QLabel('Automatisk åpning av vinduer', group)", self.install_source)
        self.assertIn('layout.insertWidget(anchor + 1, self._a3_auto_views_heading)',
                      self.install_source)

    def test_auto_open_options_are_unchanged(self):
        for caption in ('Åpne Resultatvisninger etter kjøring',
                        'Åpne Kjøredetaljer ved start', 'Åpne kjørelogg ved start'):
            self.assertIn(caption, self.install_source)
        self.assertIn('self.config.value(', self.install_source)
        self.assertIn('self.config.setValue(', self.install_source)

    def test_section_does_not_change_runner(self):
        self.assertNotIn('_run_selected(', self.install_source)
        self.assertNotIn('set_workflow(', self.install_source)


if __name__ == '__main__':
    unittest.main()
