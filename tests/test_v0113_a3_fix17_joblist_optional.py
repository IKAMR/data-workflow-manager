"""Regression checks for optional Basic job lists and Save As directory."""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.basic_joblist_suggestion_v0113_a3 import suggest_joblist_path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'basic_main_v0113_a2.py'


class FakeBase:
    def _save(self):
        self.base_save_count = getattr(self, 'base_save_count', 0) + 1
        return True

    def _start_worker(self, jobs, *, request_id=None):
        self.runner_calls = getattr(self, 'runner_calls', 0) + 1
        if not self.api.workspace().job_list_path or self.api.dirty:
            if not self._save():
                return 'blocked'
        return ('running', jobs, request_id)

    def _save_as(self):
        self.advanced_save_as = True
        return True


class FakeDialog:
    next_choice = None
    last_initial = None
    assert_dir_exists = False

    @classmethod
    def getSaveFileName(cls, _self, _title, initial, _filter):
        cls.last_initial = Path(initial)
        if cls.assert_dir_exists:
            assert cls.last_initial.parent.is_dir(), cls.last_initial.parent
        return (cls.next_choice, None)


class FakeMessage:
    class StandardButton:
        Yes = 1
        No = 2
        Cancel = 4

    choice = 0

    @classmethod
    def question(cls, *args):
        return cls.choice


def build_class():
    source = SOURCE.read_text(encoding='utf-8')
    tree = ast.parse(source)
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'DwmMainWindow')
    methods = [x for x in cls.body if isinstance(x, ast.FunctionDef)
               and x.name in ('_start_worker', '_save', '_save_as')]
    test_cls = ast.ClassDef(name='Window', bases=[ast.Name(id='FakeBase', ctx=ast.Load())],
                            keywords=[], body=methods, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[test_cls], type_ignores=[]))
    ns = dict(FakeBase=FakeBase, QMessageBox=FakeMessage, QFileDialog=FakeDialog,
              Path=Path, suggest_joblist_path=suggest_joblist_path)
    exec(compile(module, str(SOURCE), 'exec'), ns)
    return ns['Window']


Window = build_class()


class Fix17Tests(unittest.TestCase):
    def setUp(self):
        self.w = Window()
        self.w._basic_active = True
        self.w.config = SimpleNamespace(value=lambda *args: '')
        self.w.api = SimpleNamespace(settings={}, dirty=True, workspace=lambda: SimpleNamespace(job_list_path=None))
        self.w.basic_source_path = SimpleNamespace(text=lambda: '')
        self.w.basic_work_path = SimpleNamespace(text=lambda: '')
        self.w.basic_dias_label = SimpleNamespace(text=lambda: 'WebSak')
        self.w._error = lambda exc: (_ for _ in ()).throw(exc)
        self.w._remember_joblist = lambda path: None
        self.w._refresh = lambda **kwargs: None
        FakeDialog.next_choice = ''
        FakeDialog.assert_dir_exists = False

    def test_no_runs_unsaved_without_calling_save(self):
        FakeMessage.choice = FakeMessage.StandardButton.No
        self.assertEqual(self.w._start_worker([('JOB-001', False, False)]),
                         ('running', [('JOB-001', False, False)], None))
        self.assertFalse(getattr(self.w, '_a3_run_without_joblist'))
        self.assertEqual(getattr(self.w, 'base_save_count', 0), 0)

    def test_cancel_does_not_start(self):
        FakeMessage.choice = FakeMessage.StandardButton.Cancel
        self.assertIsNone(self.w._start_worker(['job']))
        self.assertEqual(getattr(self.w, 'runner_calls', 0), 0)

    def test_yes_cancelled_file_dialog_does_not_start(self):
        FakeMessage.choice = FakeMessage.StandardButton.Yes
        self.w._save_as = lambda: False
        self.assertIsNone(self.w._start_worker(['job']))
        self.assertEqual(getattr(self.w, 'runner_calls', 0), 0)

    def test_advanced_uses_original_save(self):
        self.w._basic_active = False
        self.assertEqual(self.w._start_worker(['job']), ('running', ['job'], None))
        self.assertEqual(self.w.base_save_count, 1)

    def test_missing_folder_exists_in_dialog_then_removed_on_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / 'a03'
            work.mkdir()
            self.w.basic_work_path = SimpleNamespace(text=lambda: str(work))
            FakeDialog.assert_dir_exists = True
            FakeDialog.next_choice = ''
            self.assertFalse(self.w._save_as())
            self.assertEqual(FakeDialog.last_initial.parent, work / 'jobblister')
            self.assertFalse((work / 'jobblister').exists())

    def test_save_persists_proposed_work_folder_and_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / 'a03'; work.mkdir()
            self.w.basic_work_path = SimpleNamespace(text=lambda: str(work))
            FakeDialog.assert_dir_exists = True
            def _save(path):
                assert path.parent == work / 'jobblister'
                path.write_text('example')
                return path
            self.w.api.save_job_list = _save
            proposed = suggest_joblist_path(source=None, work=work, label='WebSak')
            FakeDialog.next_choice = str(proposed)
            self.assertTrue(self.w._save_as())
            self.assertTrue(proposed.is_file())


if __name__ == '__main__':
    unittest.main()
