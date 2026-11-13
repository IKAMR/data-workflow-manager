"""Fix 15: minimal run surface and safe job-list-only Work handling."""
from pathlib import Path
import ast
import tempfile
import unittest
from app.basic_joblist_suggestion_v0113_a3 import suggest_joblist_path
from app.basic_work_guard_v0113_a3 import inspect_work, work_contains_only_joblists

ROOT = Path(__file__).resolve().parents[1]

class Fix15Tests(unittest.TestCase):
    def test_work_proposal_only_after_save_as(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / 'dwm2' / 'a03'
            proposal = suggest_joblist_path(source=root / '1525_004_source',
                work=work, label='WebSak Aknes')
            self.assertEqual(proposal.parent, work / 'jobblister')
            self.assertFalse(proposal.parent.exists())

    def test_configured_global_location_still_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preferred = root / 'my-lists'
            proposal = suggest_joblist_path(source=root / 'source', work=root / 'work',
                settings={'job_list_dir': str(preferred)})
            self.assertEqual(proposal.parent, preferred)

    def test_saved_list_only_does_not_claim_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'jobblister'; folder.mkdir()
            (folder / 'archive.n5jobs').write_text('test', encoding='utf-8')
            self.assertTrue(work_contains_only_joblists(root))
            self.assertEqual(inspect_work(root, root.parent / 'source').kind, 'empty')
            (root / 'metadata').mkdir()
            self.assertFalse(work_contains_only_joblists(root))
            self.assertEqual(inspect_work(root, root.parent / 'source').kind, 'unknown_job')

    def test_unrelated_or_bad_list_content_still_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'jobblister'; folder.mkdir()
            (folder / 'danger.txt').write_text('test', encoding='utf-8')
            self.assertFalse(work_contains_only_joblists(root))
            self.assertEqual(inspect_work(root, root.parent / 'source').kind, 'unrelated')
            (folder / 'danger.txt').unlink()
            (folder / 'subdir').mkdir()
            self.assertFalse(work_contains_only_joblists(root))

    def test_gui_shows_no_phantom_path(self):
        code = (ROOT / 'gui_qt/basic_main_v0113_a2.py').read_text(encoding='utf-8')
        tree = ast.parse(code)
        self.assertIn("joblist or 'Ikke lagret'", code)
        self.assertIn('self._a3_simplify_run_text()', code)
        self.assertIn('self.basic_workflow_description.hide()', code)
        self.assertIn('suggest_joblist_path(', code)
        self.assertIn('super()._save_as()', code)

if __name__ == '__main__':
    unittest.main()
