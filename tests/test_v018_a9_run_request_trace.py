"""Regression tests for a9 run-button decisions and diagnostic trace.

Uses the actual Qt-method bodies via AST and fake widgets, so PySide6 and the
external Noark-5/Arkade programs are not required for these behavioral tests.
"""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path
from queue import Queue
from threading import Event, Thread
from types import SimpleNamespace

from app.run_request_audit_v018_a9 import RunRequestAudit, rerun_reason

ROOT = Path(__file__).resolve().parents[1]


class FakeMessageBox:
    class StandardButton:
        Yes = 'yes'
        No = 'no'

    answer = 'yes'
    questions = []
    info = []

    @classmethod
    def question(cls, *args):
        cls.questions.append(args)
        return cls.answer

    @classmethod
    def information(cls, *args):
        cls.info.append(args)


def load_methods(*names):
    tree = ast.parse((ROOT / 'gui_qt' / 'main_window.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DwmMainWindow')
    requested = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(requested) == len(names), (len(requested), names)
    namespace = {'QMessageBox': FakeMessageBox, 'Queue': Queue, 'Event': Event,
                 'Thread': Thread, 'rerun_reason': rerun_reason,
                 'new_request_id': lambda: 'REQ-TEST-001',
                 '_is_waiting_status': lambda status: status == 'Venter ved kontrollpunkt'}
    exec(compile(ast.fix_missing_locations(ast.Module(body=requested, type_ignores=[])),
                 'gui_qt/main_window.py', 'exec'), namespace)
    return {name: namespace[name] for name in names}


METHODS = load_methods('_a9_trace_run', '_run_selected', '_start_worker')


class FakeApi:
    running = False
    dirty = False

    def __init__(self, status='Klar', progress=0.0, cursor=0, message=''):
        self.status = status
        self.progress = progress
        self.cursor = cursor
        self.message = message
        self.joblist = None
        self.run_calls = []

    def workspace(self):
        return SimpleNamespace(
            job_list_path=self.joblist,
            jobs=(SimpleNamespace(job_id='JOB-001', status=self.status,
                                  progress=self.progress, current_operation=self.cursor,
                                  operation_count=9),)
        )

    def job_details(self, job_id):
        assert job_id == 'JOB-001'
        job = self.workspace().jobs[0]
        return SimpleNamespace(job=job, message=self.message)

    def check_storage(self):
        return ()

    def run_job(self, job_id, **kwargs):
        self.run_calls.append((job_id, kwargs))
        self.status, self.progress, self.cursor = 'Ferdig', 1.0, 9
        return True


class FakeUi:
    _a9_trace_run = METHODS['_a9_trace_run']
    _run_selected = METHODS['_run_selected']
    _start_worker = METHODS['_start_worker']

    def __init__(self, root, api=None):
        self.api = api or FakeApi()
        self._active_id = 'JOB-001'
        self._worker = None
        self._job_controls_running = False
        self._run_request_busy = False
        self._run_audit = RunRequestAudit(root / 'trace.jsonl')
        self._run_audit_announced = False
        self._run_audit_warning_shown = False
        self.lines = []
        self.started = []
        self._batch_stop = Event()
        self._worker_messages = Queue()
        self._review_preflight = lambda jobs: set(jobs)
        self._save = lambda: True
        self.sender_widget = SimpleNamespace(text=lambda: 'Kjor valgt')
        self.recurse_once = False

    def sender(self):
        return self.sender_widget

    def _append_log(self, line):
        self.lines.append(line)

    def _error(self, exc):
        raise AssertionError('Unexpected UI exception: ' + str(exc))

    def _set_running_ui(self, running):
        self._job_controls_running = bool(running)

    def start_stub(self, jobs, *, request_id=None):
        self.started.append((jobs, request_id))
        if self.recurse_once:
            self.recurse_once = False
            self._run_selected()


def entries(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


class AuditUnitTests(unittest.TestCase):
    def test_new_ready_state_does_not_need_rerun(self):
        self.assertEqual(rerun_reason('Klar', ''), '')
        self.assertEqual(rerun_reason('Klar', 'Ny jobb'), '')
        self.assertEqual(rerun_reason('Venter ved kontrollpunkt', ''), '')
        self.assertEqual(rerun_reason('Ferdig', 'Workflow fullfort'), 'previous_status:Ferdig')
        self.assertEqual(rerun_reason('Klar', 'Konfigurasjon endret - klar for ny kj\u00f8ring'),
                         'workflow_changed_after_run')

    def test_one_trace_file_for_multiple_job_lists_distinguishes_identity(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'trace.jsonl'
            audit = RunRequestAudit(path)
            self.assertFalse(path.exists())
            self.assertTrue(audit.record('ui.run_clicked', request_id='A', joblist='Test-01.n5jobs', job_id='JOB-001'))
            self.assertTrue(audit.record('ui.run_clicked', request_id='B', joblist='Test-02.n5jobs', job_id='JOB-001'))
            records = entries(path)
            self.assertEqual({x['request_id'] for x in records}, {'A', 'B'})
            self.assertNotEqual(records[0]['joblist'], records[1]['joblist'])
            self.assertEqual(len({x['session_id'] for x in records}), 1)
            self.assertTrue(records[0]['timestamp_utc'].endswith('+00:00'))

    def test_unknown_fields_and_source_data_not_written(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'trace.jsonl'
            RunRequestAudit(path).record('ui.first_run', secret_password='NOT-A-LOG', source_bytes=b'private')
            self.assertNotIn('NOT-A-LOG', path.read_text(encoding='utf8'))
            self.assertNotIn('private', path.read_text(encoding='utf8'))


class GuiDecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        FakeMessageBox.questions = []
        FakeMessageBox.info = []
        FakeMessageBox.answer = FakeMessageBox.StandardButton.Yes
        self.ui = FakeUi(self.root)
        self.ui._start_worker = self.ui.start_stub

    def test_first_run_one_click_no_rerun_prompt(self):
        self.ui._run_selected()
        self.assertEqual(len(FakeMessageBox.questions), 0)
        self.assertEqual(self.ui.started, [([('JOB-001', False, False)], 'REQ-TEST-001')])
        self.assertEqual(self.ui._run_request_busy, False)
        events = [r['event'] for r in entries(self.ui._run_audit.path)]
        self.assertIn('ui.first_run', events)
        self.assertNotIn('ui.rerun_prompt_shown', events)

    def test_completed_job_dialog_records_why(self):
        self.ui.api = FakeApi('Ferdig', 1.0, 9, 'Workflow fullf\u00f8rt')
        self.ui._run_selected()
        self.assertEqual(len(FakeMessageBox.questions), 1)
        self.assertEqual(self.ui.started, [([('JOB-001', True, False)], 'REQ-TEST-001')])
        reasons = [r.get('reason') for r in entries(self.ui._run_audit.path)
                   if r['event'] == 'ui.rerun_prompt_shown']
        self.assertEqual(reasons, ['previous_status:Ferdig'])

    def test_declined_rerun_does_not_start(self):
        self.ui.api = FakeApi('Ferdig', 1.0, 9)
        FakeMessageBox.answer = FakeMessageBox.StandardButton.No
        self.ui._run_selected()
        self.assertEqual(self.ui.started, [])
        self.assertIn('no', [r.get('decision') for r in entries(self.ui._run_audit.path)])

    def test_reentrant_click_is_ignored_during_request(self):
        self.ui.recurse_once = True
        self.ui._run_selected()
        self.assertEqual(len(self.ui.started), 1)
        records = entries(self.ui._run_audit.path)
        self.assertEqual(sum(r['event'] == 'ui.run_ignored' for r in records), 1)
        self.assertFalse(self.ui._run_request_busy)

    def test_busy_worker_does_not_prompt_or_start(self):
        self.ui._worker = object()
        self.ui._run_selected()
        self.assertEqual(self.ui.started, [])
        self.assertEqual(len(FakeMessageBox.questions), 0)

    def test_unsaved_list_is_logged_without_mutating_joblist(self):
        self.ui._run_selected()
        log = entries(self.ui._run_audit.path)
        self.assertEqual(log[0]['joblist'], '(ikke lagret)')
        self.assertFalse((self.root / 'JOB-001.n5jobs').exists())


class WorkerTraceTests(unittest.TestCase):
    def test_actual_worker_attempt_has_same_request_id_and_records_result(self):
        with tempfile.TemporaryDirectory() as root:
            ui = FakeUi(Path(root))
            ui.api.joblist = str(Path(root) / 'new-list.n5jobs')
            ui._start_worker([('JOB-001', False, False)], request_id='REQ-WORKER')
            ui._worker.join(timeout=3)
            self.assertFalse(ui._worker.is_alive())
            self.assertEqual(len(ui.api.run_calls), 1)
            self.assertEqual(ui.api.run_calls[0][1]['allow_rerun'], False)
            log = entries(ui._run_audit.path)
            stages = [r['event'] for r in log]
            self.assertIn('ui.preflight_started', stages)
            self.assertIn('ui.worker_queued', stages)
            self.assertIn('worker.started', stages)
            self.assertIn('api.run_job_called', stages)
            self.assertIn('api.run_job_returned', stages)
            self.assertIn('worker.finished', stages)
            self.assertEqual({r['request_id'] for r in log}, {'REQ-WORKER'})
            self.assertTrue(all(r['joblist'] == str(Path(root) / 'new-list.n5jobs') for r in log))
            self.assertEqual(ui.api.status, 'Ferdig')

    def test_cancelled_preflight_never_starts_worker(self):
        with tempfile.TemporaryDirectory() as root:
            ui = FakeUi(Path(root))
            ui._review_preflight = lambda jobs: None
            ui._start_worker([('JOB-001', False, False)], request_id='REQ-CANCEL')
            self.assertIsNone(ui._worker)
            self.assertEqual(ui.api.run_calls, [])
            self.assertIn('ui.preflight_cancelled', [r['event'] for r in entries(ui._run_audit.path)])


if __name__ == '__main__':
    unittest.main()
