"""Fix10: no Work ownership inferred from proximity, recovery uses shared API."""
from __future__ import annotations
import ast
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from app.basic_work_guard_v0113_a3 import inspect_work, nearby_job_lists

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / 'gui_qt' / 'basic_main_v0113_a2.py'

class WorkRecoveryTests(unittest.TestCase):
    def test_local_lists_are_candidates_not_proof(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            work = root / 'repository_operations' / 'dwm2' / 'a02'
            work.mkdir(parents=True)
            candidate = work / 'project.n5jobs'
            candidate.write_text('not verified', encoding='utf-8')
            found = nearby_job_lists(work)
            self.assertEqual(len(found), 1)
            self.assertTrue(os.path.samefile(found[0], candidate))
            self.assertEqual(inspect_work(work, root / 'source').kind, 'unknown_job')

    def test_search_is_bounded_to_nearby_parents(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            work = root / 'container' / 'a02'
            work.mkdir(parents=True)
            (root / 'other.n5jobs').write_text('outside bounded search', encoding='utf-8')
            found = nearby_job_lists(work)
            self.assertEqual(len(found), 1)
            self.assertTrue(os.path.samefile(found[0], root / 'other.n5jobs'))

    def test_gui_blocks_different_source_and_offers_recovery(self):
        source = GUI.read_text('utf-8')
        ast.parse(source)
        self.assertIn("if kind == 'different_source':", source)
        self.assertIn("if kind == 'unknown_job':", source)
        self.assertIn("if kind == 'same_job' and match is None:", source)
        self.assertIn('def _a3_offer_existing_work(', source)
        self.assertIn('self._open_path(filename)', source)
        self.assertIn('_same(job_source, plan.source_extraction)', source)
        self.assertIn('_same(job_work, plan.work_operations)', source)
        self.assertIn('Kontroller valgte operasjoner før ny kjøring.', source)

if __name__ == '__main__':
    unittest.main()
