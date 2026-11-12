"""a3.5: Basic progress reflects real runner events, never a fake percent.

These tests deliberately do not require PySide6; UI integration is then
verified by test.bat on Windows and interactive testing of the running GUI.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from app.basic_run_feedback_v0111_a3 import (
    latest_signal_text, operation_caption, sanitized_activity_message,
)

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / 'gui_qt' / 'basic_main_v0111_a1.py'
SF_OP = ROOT / 'noark5_workflow' / 'operations' / 'run_siegfried_pronom.py'
SF_LIB = ROOT / 'app' / 'siegfried_tool_v0111_a3.py'


class LiveProgressTests(unittest.TestCase):
    def test_caption_shows_real_operation_name_and_cursor(self):
        operations = [SimpleNamespace(name='Noark 5-kontroller'),
                      SimpleNamespace(name='Siegfried – PRONOM'),
                      SimpleNamespace(name='Arkade 5')]
        self.assertEqual(operation_caption(operations, 1, 3),
                         'Aktiv deljobb 2 av 3: Siegfried – PRONOM')
        self.assertEqual(operation_caption(operations, 3, 3),
                         '3 av 3 deljobber fullført.')
        self.assertEqual(operation_caption((), 0, 0), 'Klargjør kontrollene ...')

    def test_last_signal_is_staleness_not_fabricated_progress(self):
        self.assertIn('Ingen kjøremelding', latest_signal_text(None, 50))
        self.assertIn('5 sek', latest_signal_text(10, 15))
        self.assertIn('2 min 1 sek', latest_signal_text(10, 131))
        self.assertIn('kan fortsatt arbeide', latest_signal_text(10, 131))

    def test_log_feedback_only_displays_bounded_appropriate_text(self):
        self.assertEqual(sanitized_activity_message('START: Arkade', 'run.log'),
                         'START: Arkade')
        self.assertEqual(sanitized_activity_message('{"large": "json"}', 'run.log'), '')
        self.assertEqual(sanitized_activity_message('[Arkade 5/PRONOM] some text', 'run.log'),
                         'Mottar kjørelogg fra Arkade 5.')
        self.assertLessEqual(len(sanitized_activity_message('a'*500, 'run.progress')), 210)
        self.assertEqual(sanitized_activity_message('Fil 35 av 130\nHemmelig', 'run.progress'),
                         'Fil 35 av 130')

    def test_gui_receives_run_events_on_qt_thread_with_real_step_progress(self):
        tree = ast.parse(GUI.read_text(encoding='utf-8'))
        window = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                      and x.name == 'DwmMainWindow')
        events = next(x for x in window.body if isinstance(x, ast.FunctionDef)
                      and x.name == '_a8_process_run_event')
        text = ast.get_source_segment(GUI.read_text(encoding='utf-8'), events)
        self.assertIn("super()._a8_process_run_event(event)", text)
        self.assertIn("event, 'job_id'", text)
        self.assertIn("kind == 'run.progress'", text)
        self.assertIn("self._basic_operation_fraction = float(value)", text)
        self.assertIn("time.monotonic()", text)
        sync = next(x for x in window.body if isinstance(x, ast.FunctionDef)
                    and x.name == '_sync_basic_status')
        code = ast.get_source_segment(GUI.read_text(encoding='utf-8'), sync)
        self.assertIn("self.basic_operation_progress.setRange(0, 0)", code)
        self.assertIn("self.basic_operation_progress.setRange(0, 100)", code)
        self.assertIn("self.basic_active_operation.setText", code)
        self.assertIn("latest_signal_text(", code)
        self.assertIn("self._basic_operation_index != completed", code)
        self.assertNotIn("self._basic_operation_fraction +=", code)
        self.assertIn("setInterval(500)", GUI.read_text(encoding='utf-8'))

    def test_event_handler_ignores_another_job(self):
        # Dynamically exercise the real method, without importing Qt widgets.
        source = GUI.read_text(encoding='utf-8')
        cls = next(x for x in ast.parse(source).body if isinstance(x, ast.ClassDef)
                   and x.name == 'DwmMainWindow')
        fun = next(x for x in cls.body if isinstance(x, ast.FunctionDef)
                   and x.name == '_a8_process_run_event')
        base = type('Base', (), {'_a8_process_run_event': lambda self, ev: None})
        fragment = ast.Module(body=[ast.ClassDef(
            name='FakeWindow', bases=[ast.Name(id='Base', ctx=ast.Load())],
            keywords=[], body=[fun], decorator_list=[])], type_ignores=[])
        ast.fix_missing_locations(fragment)
        import time
        ns = {'Base': base, 'time': time, 'sanitized_activity_message': sanitized_activity_message}
        exec(compile(fragment, '<test-qt-free>', 'exec'), ns)
        win = ns['FakeWindow']()
        win._basic_job_id = 'JOB-001'
        win._basic_last_run_signal = None
        win._basic_operation_fraction = None
        win._basic_operation_index = None
        win._basic_last_run_message = ''
        win._a8_process_run_event(SimpleNamespace(
            job_id='JOB-002', kind='run.progress', progress=.9, message='other'))
        self.assertIsNone(win._basic_operation_fraction)
        win._a8_process_run_event(SimpleNamespace(
            job_id='JOB-001', kind='run.progress', progress=.42,
            message='Siegfried: 42 av 100 filer identifisert'))
        self.assertEqual(win._basic_operation_fraction, .42)
        self.assertIn('42 av 100', win._basic_last_run_message)
        self.assertIsInstance(win._basic_last_run_signal, float)
        win._a8_process_run_event(SimpleNamespace(
            job_id='JOB-001', kind='run.log', message='START: Arkade 5'))
        self.assertIsNone(win._basic_operation_fraction)
        self.assertEqual(win._basic_last_run_message, 'START: Arkade 5')


    def test_live_status_widget_shows_measured_progress_not_elapsed_time(self):
        source = GUI.read_text(encoding='utf-8')
        cls = next(x for x in ast.parse(source).body if isinstance(x, ast.ClassDef)
                   and x.name == 'DwmMainWindow')
        fun = next(x for x in cls.body if isinstance(x, ast.FunctionDef)
                   and x.name == '_sync_basic_status')
        fragment = ast.Module(body=[ast.ClassDef(
            name='FakeWindow', bases=[], keywords=[], body=[fun],
            decorator_list=[])], type_ignores=[])
        ast.fix_missing_locations(fragment)
        import time
        ns = {'time': time, 'operation_caption': operation_caption,
              'latest_signal_text': latest_signal_text}
        exec(compile(fragment, '<test-qt-status>', 'exec'), ns)
        class Control:
            def __init__(self, value=''):
                self.value = value
                self.enabled = None
                self.visible = None
                self.rng = None
            def setText(self, value): self.value = value
            def text(self): return self.value
            def setEnabled(self, value): self.enabled = value
            def setVisible(self, value): self.visible = value
            def setRange(self, lo, hi): self.rng = (lo, hi)
            def setValue(self, value): self.value = value

        win = ns['FakeWindow']()
        for key in ('basic_run_button','basic_choose_source','basic_choose_work',
                    'basic_stop_button','basic_active_operation',
                    'basic_operation_progress','basic_activity',
                    'basic_source_path','basic_work_path','basic_results_button',
                    'basic_progress','basic_status'):
            setattr(win, key, Control())
        win.basic_source_path.value = '/source'
        win.basic_work_path.value = '/work'
        win._selected_basic_controls = lambda: ('dwm',)
        win._basic_legacy_layout = False
        win._basic_starting = False
        win._basic_job_id = 'JOB-001'
        win._worker = object()
        win._basic_operation_index = 1
        win._basic_operation_fraction = .42
        win._basic_heartbeat_tick = 0
        win._basic_last_run_signal = time.monotonic() - 2
        win._basic_last_run_message = 'Siegfried: 42 av 100 filer identifisert'
        job = SimpleNamespace(job_id='JOB-001', status='Kjører', progress=.10,
                              current_operation=1, operation_count=10)
        operations = [SimpleNamespace(name=f'Steg {k}') for k in range(10)]
        win.api = SimpleNamespace(
            running=True,
            workspace=lambda: SimpleNamespace(jobs=(job,)),
            job_details=lambda _id: SimpleNamespace(operations=operations))
        win._sync_basic_status()
        self.assertEqual(win.basic_progress.value, 10)
        self.assertEqual(win.basic_operation_progress.rng, (0, 100))
        self.assertEqual(win.basic_operation_progress.value, 42)
        self.assertIn('Aktiv deljobb 2 av 10: Steg 1', win.basic_active_operation.value)
        self.assertIn('42 av 100', win.basic_activity.value)
        self.assertIn('1 av 10 deljobber fullført', win.basic_status.value)
        # When the job moves to its next operation, stale measured progress
        # from the previous operation must not leak into the new step.
        job.current_operation = 2
        win._sync_basic_status()
        self.assertEqual(win.basic_operation_progress.rng, (0, 0))
        self.assertEqual(win.basic_progress.value, 10)
        win._worker = None
        win.api.running = False
        win._sync_basic_status()
        self.assertFalse(win.basic_operation_progress.visible)

    def test_siegfried_discovery_emits_real_file_counts(self):
        # Extract the standalone function to test without registry dependencies.
        tree = ast.parse(SF_OP.read_text(encoding='utf-8'))
        fun = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == 'document_files')
        fragment = ast.Module(body=[fun], type_ignores=[])
        ast.fix_missing_locations(fragment)
        import os
        ns = {'Path': Path, 'os': os, 'MAX_FILES_PER_SCAN': 250_000}
        exec(compile(fragment, '<test-discovery>', 'exec'), ns)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            doc = root/'DOKUMENT';doc.mkdir()
            for i in range(5):
                (doc/f'{i}.pdf').write_bytes(b'%PDF')
            callbacks = []
            files, scope = ns['document_files'](root, progress_cb=callbacks.append,
                                                progress_interval=2)
            self.assertEqual(len(files), 5)
            self.assertEqual(callbacks, [2, 4, 5])
            self.assertEqual(scope, 'DOKUMENT')

    def test_siegfried_cli_emits_file_count_after_completed_batch(self):
        tool = SF_LIB.read_text(encoding='utf-8')
        self.assertIn('file_progress_cb: Callable[[int, int], None]', tool)
        self.assertIn('file_progress_cb(done_files, len(files))', tool)
        op = SF_OP.read_text(encoding='utf-8')
        self.assertIn("f'Siegfried: {done} av {total} filer analysert'", op)
        self.assertIn("f'Finner dokumentfiler: {found} filer funnet'", op)


if __name__ == '__main__':
    unittest.main()
