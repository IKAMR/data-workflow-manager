"""v0.2.2-a1.4: 'Ny kontroll' is a safe fresh start in Enkel modus.

Tests execute the real GUI method against a minimal window harness, without
requiring PySide6 on CI/Linux. Full Windows Qt visual testing is still needed.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / 'gui_qt/basic_multijob_v022_a1_2.py'


class Message:
    class StandardButton:
        Yes, No, Save, Discard, Cancel = 1, 2, 4, 8, 16

    responses = []
    dialogs = []
    @classmethod
    def question(cls, _parent, title, body, *args):
        cls.dialogs.append((title, body))
        if not cls.responses:
            raise AssertionError('Unexpected confirmation: ' + title)
        return cls.responses.pop(0)

    @classmethod
    def information(cls, _parent, title, body):
        cls.dialogs.append((title, body))

    @classmethod
    def warning(cls, _parent, title, body):
        cls.dialogs.append((title, body))


class Field:
    def __init__(self, value=''):
        self.value = str(value)
    def text(self):
        return self.value
    def clear(self):
        self.value = ''
    def setText(self, value):
        self.value = str(value)


class FakeAPI:
    def __init__(self, *, jobs=(), filename=None, fail_save=False, fail_new=False):
        self.jobs = list(jobs)
        self.filepath = Path(filename) if filename else None
        self.fail_save = fail_save
        self.fail_new = fail_new
        self.running = False
        self.new_count = 0
        self.saves = 0

    def workspace(self):
        return types.SimpleNamespace(jobs=tuple(self.jobs), job_list_path=self.filepath)

    def save_job_list(self, path=None):
        if self.fail_save:
            raise OSError('Simulated full disk')
        if path:
            self.filepath = Path(path)
        if not self.filepath:
            raise RuntimeError('No filename')
        self.filepath.write_text(json.dumps({'jobs': self.jobs}), encoding='utf-8')
        self.saves += 1
        return self.filepath

    def new_job_list(self):
        if self.fail_new:
            raise RuntimeError('Simulated API failure')
        self.jobs = []
        self.filepath = None
        self.new_count += 1


class Base:
    def _save_as(self):
        self.save_as_called += 1
        if self.cancel_save_as:
            return False
        self.api.save_job_list(self.save_as_target)
        return True


def compiled_gui_method():
    code = GUI.read_text(encoding='utf-8')
    tree = ast.parse(code)
    classdef = next(node for node in tree.body
                    if isinstance(node, ast.ClassDef) and node.name == 'DwmMainWindow')
    function = next(node for node in classdef.body
                    if isinstance(node, ast.FunctionDef) and node.name == '_a3_new_control')
    harness = ast.ClassDef(name='ResetHarness', bases=[ast.Name(id='Base', ctx=ast.Load())],
                           keywords=[], body=[function], decorator_list=[])
    scope = {'Base': Base, 'QMessageBox': Message}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[harness], type_ignores=[])),
                 str(GUI), 'exec'), scope)
    return scope['ResetHarness']


ResetHarness = compiled_gui_method()


class Window(ResetHarness):
    def __init__(self, api, folder):
        self.api = api
        self._worker = None
        self._active_id = 'JOB-001' if api.jobs else None
        self._basic_job_id = self._active_id
        self._v022_draft = not bool(self._active_id)
        self._basic_legacy_layout = False
        self._basic_selection_edited = False
        self._a2_pending_dirty = False
        self.basic_source_path = Field('C:/source' if self._active_id else '')
        self.basic_work_path = Field('C:/work' if self._active_id else '')
        self.basic_dias_label = Field()
        self.basic_dias_note = Field()
        self._v022_loading_job = False
        self._v022_save_failed = False
        self._v022_register_calls = 0
        self._v022_register_success = True
        self.cancel_save_as = False
        self.save_as_called = 0
        self.save_as_target = folder/'fresh_old.n5jobs'
        self.config = types.SimpleNamespace(setValue=lambda *a: None)
        self._refresh_recent_menu = lambda: None
        self._refresh = lambda **kw: None
        self._v022_refresh_selector = lambda **kw: None
        self._a2_set_step = lambda x: setattr(self, 'step', x)

    def _v022_register_current(self):
        self._v022_register_calls += 1
        return self._v022_register_success

    def _v022_save_joblist_to_existing_file(self, *, force=False):
        try:
            self.api.save_job_list()
        except OSError:
            Message.warning(self, 'Lagring feilet', 'Kunne ikke lagre')
            return False
        return True

    def _reset_basic_selection(self):
        self.basic_source_path.clear()
        self.basic_work_path.clear()
        self._basic_job_id = None


class FreshStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        Message.responses.clear()
        Message.dialogs.clear()

    def saved_window(self, *, fail_save=False):
        filename = self.folder/'saved.n5jobs'
        filename.write_text('OLD VERSION', encoding='utf-8')
        return Window(FakeAPI(jobs=['JOB-001', 'JOB-002', 'JOB-003'],
                              filename=filename, fail_save=fail_save), self.folder)

    def test_new_control_resets_only_active_workspace_and_keeps_saved_file(self):
        window = self.saved_window()
        Message.responses = [Message.StandardButton.Yes]
        self.assertTrue(window._a3_new_control())
        self.assertEqual(window.api.new_count, 1)
        self.assertEqual(window.api.jobs, [])
        self.assertIsNone(window.api.filepath)
        self.assertEqual(window.basic_source_path.text(), '')
        self.assertEqual(window.basic_work_path.text(), '')
        self.assertTrue(window._v022_draft)
        self.assertEqual(window.step, 'source')
        self.assertEqual(json.loads((self.folder/'saved.n5jobs').read_text())['jobs'],
                         ['JOB-001', 'JOB-002', 'JOB-003'])
        self.assertEqual(window.api.saves, 1)

    def test_no_leaves_everything_unchanged(self):
        window = self.saved_window()
        Message.responses = [Message.StandardButton.No]
        self.assertFalse(window._a3_new_control())
        self.assertEqual(window.api.new_count, 0)
        self.assertEqual(window.api.saves, 0)
        self.assertTrue(window.basic_source_path.text())

    def test_save_failure_cannot_clear_unsaved_work(self):
        window = self.saved_window(fail_save=True)
        Message.responses = [Message.StandardButton.Yes]
        self.assertFalse(window._a3_new_control())
        self.assertEqual(window.api.new_count, 0)
        self.assertEqual(window.api.jobs, ['JOB-001', 'JOB-002', 'JOB-003'])
        self.assertEqual((self.folder/'saved.n5jobs').read_text(), 'OLD VERSION')

    def test_cancel_file_picker_preserves_unsaved_control(self):
        window = Window(FakeAPI(jobs=['JOB-001', 'JOB-002']), self.folder)
        window.cancel_save_as = True
        Message.responses = [Message.StandardButton.Yes, Message.StandardButton.Save]
        self.assertFalse(window._a3_new_control())
        self.assertEqual(window.api.new_count, 0)
        self.assertEqual(window.save_as_called, 1)
        self.assertEqual(window.api.jobs, ['JOB-001', 'JOB-002'])

    def test_unsaved_jobs_are_saved_before_reset(self):
        window = Window(FakeAPI(jobs=['JOB-001', 'JOB-002']), self.folder)
        Message.responses = [Message.StandardButton.Yes, Message.StandardButton.Save]
        self.assertTrue(window._a3_new_control())
        self.assertEqual(window.api.new_count, 1)
        self.assertEqual(json.loads(window.save_as_target.read_text())['jobs'],
                         ['JOB-001', 'JOB-002'])

    def test_explicit_discard_is_possible_for_unsaved_control(self):
        window = Window(FakeAPI(jobs=['JOB-001']), self.folder)
        Message.responses = [Message.StandardButton.Yes, Message.StandardButton.Discard]
        self.assertTrue(window._a3_new_control())
        self.assertEqual(window.api.new_count, 1)
        self.assertFalse(window.save_as_target.exists())

    def test_unsaved_job_can_cancel_without_loss(self):
        window = Window(FakeAPI(jobs=['JOB-001']), self.folder)
        Message.responses = [Message.StandardButton.Yes, Message.StandardButton.Cancel]
        self.assertFalse(window._a3_new_control())
        self.assertEqual(window.api.new_count, 0)

    def test_partial_draft_confirmation_without_other_jobs(self):
        window = Window(FakeAPI(), self.folder)
        window.basic_source_path.setText('C:/only_source')
        window._a2_pending_dirty = True
        Message.responses = [Message.StandardButton.Yes]
        self.assertTrue(window._a3_new_control())
        self.assertEqual(window.basic_source_path.text(), '')
        self.assertEqual(window.api.new_count, 1)
        self.assertTrue(any('ufullstendige' in d[1] for d in Message.dialogs))

    def test_running_job_cannot_be_reset(self):
        window = self.saved_window()
        window.api.running = True
        self.assertFalse(window._a3_new_control())
        self.assertEqual(window.api.new_count, 0)

    def test_clean_completed_job_does_not_rewrite_its_workflow(self):
        window = self.saved_window()
        window._basic_selection_edited = False
        Message.responses = [Message.StandardButton.Yes]
        self.assertTrue(window._a3_new_control())
        self.assertEqual(window._v022_register_calls, 0)

    def test_pending_edits_register_before_reset(self):
        window = self.saved_window()
        window._basic_selection_edited = True
        Message.responses = [Message.StandardButton.Yes]
        self.assertTrue(window._a3_new_control())
        self.assertEqual(window._v022_register_calls, 1)

    def test_failed_pending_edit_save_blocks_reset(self):
        window = self.saved_window()
        window._basic_selection_edited = True
        window._v022_register_success = False
        Message.responses = [Message.StandardButton.Yes]
        self.assertFalse(window._a3_new_control())
        self.assertEqual(window.api.new_count, 0)

    def test_legacy_job_may_reset_without_re_registration(self):
        window = self.saved_window()
        window._basic_legacy_layout = True
        Message.responses = [Message.StandardButton.Yes]
        self.assertTrue(window._a3_new_control())
        self.assertEqual(window._v022_register_calls, 0)

    def test_new_list_failure_does_not_clear_gui(self):
        window = self.saved_window()
        window.api.fail_new = True
        Message.responses = [Message.StandardButton.Yes]
        self.assertFalse(window._a3_new_control())
        self.assertTrue(window.basic_source_path.text())
        self.assertEqual(window.api.new_count, 0)

    def test_new_ui_shows_distinct_actions_without_joblist_jargon(self):
        source = GUI.read_text(encoding='utf-8')
        self.assertIn("self.basic_new_control_button.show()", source)
        self.assertIn("QPushButton('Legg til nytt uttrekk'", source)
        self.assertIn("setText('Ny kontroll')", source)
        self.assertIn("QGroupBox('Uttrekk i kontrollen'", source)
        self.assertIn("QPushButton('Lagre'", source)
        self.assertIn("QPushButton('Lagre som…'", source)


if __name__ == '__main__':
    unittest.main()
