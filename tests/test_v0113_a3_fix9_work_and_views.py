"""Fix9 contracts: non-destructive Work policy and Basic-only auto views."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from app.basic_work_guard_v0113_a3 import inspect_work

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / 'gui_qt' / 'basic_main_v0113_a2.py'


class WorkGuardTests(unittest.TestCase):
    def test_absent_and_empty(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(inspect_work(root / 'new', root / 'src').kind, 'empty')
            work = root / 'empty'
            work.mkdir()
            self.assertEqual(inspect_work(work, root / 'src').kind, 'empty')

    def test_unrelated_content_is_distinguished(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'notes.txt').write_text('Do not remove', encoding='utf-8')
            result = inspect_work(root, root / 'source')
            self.assertEqual(result.kind, 'unrelated')
            self.assertIn('notes.txt', result.summary())
            self.assertEqual((root / 'notes.txt').read_text(encoding='utf-8'), 'Do not remove')

    def test_detect_other_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / 'work'
            work.mkdir()
            (work / 'job.json').write_text(json.dumps({'job': {'source_extraction': str(root / 'other')}}), encoding='utf-8')
            result = inspect_work(work, root / 'desired')
            self.assertEqual(result.kind, 'different_source')
            self.assertIn('other', result.recorded_source)

    def test_recognizes_matching_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / 'work'
            work.mkdir()
            (work / 'job.json').write_text(json.dumps({'job': {'source_extraction': str(root / 'desired')}}), encoding='utf-8')
            self.assertEqual(inspect_work(work, root / 'desired').kind, 'same_job')

    def test_unknown_job_is_blocked(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'wf').mkdir()
            self.assertEqual(inspect_work(root, root / 'source').kind, 'unknown_job')
            (root / 'job.json').write_text('{broken', encoding='utf-8')
            self.assertEqual(inspect_work(root, root / 'source').kind, 'unknown_job')


class GuiContractTests(unittest.TestCase):
    def test_runtime_compiles_and_auto_choices_are_basic_only(self):
        source = GUI.read_text(encoding='utf-8')
        tree = ast.parse(source)
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'DwmMainWindow')
        names = {x.name for x in cls.body if isinstance(x, ast.FunctionDef)}
        for name in ('_a3_accept_work', '_choose_basic_work', '_a3_install_auto_views',
                     '_a3_create_approved_job', '_a3_auto_start_windows', '_start_basic_control'):
            self.assertIn(name, names)
        for val in ('Åpne Resultatvisninger etter kjøring', 'Åpne Kjøredetaljer ved start',
                    'Åpne kjørelogg ved start', 'inspect_work('):
            self.assertIn(val, source)
        self.assertIn("self._a3_auto_results_pending = False", source)
        self.assertIn("if kind == 'different_source':", source)
        self.assertIn("if kind == 'unknown_job':", source)
        self.assertIn('Velg uttrekksmappe eller les info.xml. Rekkefølgen er valgfri.', source)


if __name__ == '__main__':
    unittest.main()
