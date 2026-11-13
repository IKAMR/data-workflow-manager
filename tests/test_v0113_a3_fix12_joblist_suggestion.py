"""Qt-free regression checks for Basic Save As defaults."""
from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest

from app.basic_joblist_suggestion_v0113_a3 import suggest_joblist_path

ROOT = Path(__file__).resolve().parents[1]


class JoblistProposalTests(unittest.TestCase):
    def test_adjacent_operations_directory_and_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            extraction = Path(tmp) / '1525_004_E-1525-2025-0001'
            (extraction / 'repository_operations').mkdir(parents=True)
            source = extraction / 'content' / 'sip' / 'content'
            proposal = suggest_joblist_path(source=source, work=None,
                label='1525_004 WebSak Åknes1–3 (2008–2022)')
            self.assertEqual(proposal.parent, extraction / 'repository_operations' / 'jobblister')
            self.assertTrue(proposal.name.startswith('1525_004_WebSak_Aaknes1-3'))
            self.assertFalse(proposal.parent.exists(), 'The suggestion must not create the folder')

    def test_setup_override_takes_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            configured = Path(tmp) / 'configured'
            proposal = suggest_joblist_path(source=Path(tmp)/'some-source',work=None,
                label='Archive', settings={'job_list_dir': str(configured)})
            self.assertEqual(proposal, configured / 'Archive.n5jobs')
            self.assertFalse(configured.exists())

    def test_ignored_content_label_and_work_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / 'repository_operations' / 'dwm2' / 'a03'
            result = suggest_joblist_path(source=Path(tmp)/'1525_004_content',
                                          work=work, label='content')
            self.assertEqual(result.parent, work / 'jobblister')
            self.assertEqual(result.name, '1525_004.n5jobs')

    def test_no_work_or_repository_keeps_suggestion_outside_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'
            source.mkdir()
            proposed = suggest_joblist_path(source=source, work=None)
            self.assertEqual(proposed.parent, Path(tmp)/'repository_operations'/'jobblister')

    def test_no_context_does_not_guess_git_directory(self):
        self.assertIsNone(suggest_joblist_path(source=None, work=None))

    def test_gui_save_as_uses_suggestion_and_does_not_change_advanced(self):
        code = (ROOT / 'gui_qt' / 'basic_main_v0113_a2.py').read_text('utf-8')
        tree = ast.parse(code)
        methods = [node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name == '_save_as']
        self.assertEqual(len(methods), 1)
        body = ast.get_source_segment(code, methods[0])
        self.assertIn('super()._save_as()', body)
        self.assertIn('suggest_joblist_path(', body)
        self.assertLess(body.index('getSaveFileName('), body.index('target.parent.mkdir('))


if __name__ == '__main__':
    unittest.main()
