"""Exercise the A10 Qt controller contract using minimal fake Qt modules."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class TestA10WindowWithoutQt(unittest.TestCase):
    def setUp(self):
        qt = types.ModuleType('PySide6')
        core = types.ModuleType('PySide6.QtCore')
        core.Qt = types.SimpleNamespace(Orientation=types.SimpleNamespace(Vertical=1, Horizontal=2))
        widgets = types.ModuleType('PySide6.QtWidgets')

        class Message:
            class StandardButton:
                Yes, No = 1, 2
            question_text = ''
            @classmethod
            def question(cls, _parent, _title, text, *_args):
                cls.question_text = text
                return cls.StandardButton.Yes
            @staticmethod
            def information(*args):
                return None
            @staticmethod
            def warning(*args):
                return None

        self.message = Message
        for name in ('QFileDialog','QHeaderView','QInputDialog','QPushButton'):
            setattr(widgets, name, type(name, (), {}))
        widgets.QMessageBox = Message

        class PreviousWindow:
            def _v022_register_current(self, *, show_errors=True):
                if getattr(self, '_stub_create', False):
                    self.api.jobs.append(types.SimpleNamespace(
                        job_id='JOB-002', name='content',
                        source_extraction='folder/1525_005/content/sip/content'))
                return True

        base = types.ModuleType('gui_qt.basic_multijob_v022_a1_2')
        base.DwmMainWindow = PreviousWindow
        self.patch = patch.dict(sys.modules, {
            'PySide6': qt, 'PySide6.QtCore': core,
            'PySide6.QtWidgets': widgets,
            'gui_qt.basic_multijob_v022_a1_2': base,
        })
        self.patch.start()
        self.addCleanup(self.patch.stop)
        spec = importlib.util.spec_from_file_location(
            'test_dynamic_a10_window', ROOT / 'gui_qt/main_v022_a10.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.cls = module.DwmMainWindow

    def test_ready_batch_uses_single_existing_worker_and_ordered_confirmation(self):
        jobs = [types.SimpleNamespace(job_id='JOB-001', name='First', status='Ferdig'),
                types.SimpleNamespace(job_id='JOB-002', name='Second', status='Klar'),
                types.SimpleNamespace(job_id='JOB-003', name='Third', status='Klar')]
        class Api:
            running = False
            def workspace(self): return types.SimpleNamespace(jobs=jobs)
            def job_details(self, ident):
                return types.SimpleNamespace(message='Klar')
        window = self.cls.__new__(self.cls)
        window.api = Api()
        window._worker = None
        started = []
        window._start_worker = lambda tasks: started.append(tasks)
        window._run_ready()
        self.assertEqual(started, [[('JOB-002',False,False),('JOB-003',False,False)]])
        self.assertIn('JOB-002: Second', self.message.question_text)
        self.assertIn('JOB-003: Third', self.message.question_text)
        self.assertIn('f\u00f8rste tekniske feil', self.message.question_text)

    def test_batch_guard_is_active_during_preflight_before_worker_exists(self):
        window = self.cls.__new__(self.cls)
        jobs = [types.SimpleNamespace(job_id='JOB-001', name='Sample', status='Klar')]
        window.api = types.SimpleNamespace(running=False,
                                           workspace=lambda: types.SimpleNamespace(jobs=jobs))
        window._worker = None
        window._job_controls_running = True
        starts = []
        window._start_worker = lambda tasks: starts.append(tasks)
        window._run_ready()
        self.assertFalse(starts)
        class Action:
            enabled = None
            def setText(self, text): self.text = text
            def setEnabled(self, flag): self.enabled = flag
        window.ready_action = Action()
        window._a10_refresh_labels()
        self.assertEqual(window.ready_action.text, 'Kj\u00f8r alle klare (1)')
        self.assertFalse(window.ready_action.enabled)

    def test_info_file_limits_source_choice_to_matching_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a = root / '1525_004'
            b = root / '1525_006'
            a.mkdir()
            b.mkdir()
            info = a / '1525_004_abc_info.xml'
            info.touch()
            extracted = a / 'content' / 'sip' / 'content'
            extracted.mkdir(parents=True)
            (extracted / 'arkivstruktur.xml').touch()
            (b / 'arkivstruktur.xml').touch()
            fake_check = types.ModuleType('app.job_preflight_v018_a6')
            fake_check.check_extraction_folder = lambda source, profile_id: ()
            with patch.dict(sys.modules, {'app.job_preflight_v018_a6': fake_check}):
                window = self.cls.__new__(self.cls)
                window._worker = None
                window.api = types.SimpleNamespace(running=False)
                window._a2_original = info
                window._a3_manually_loaded_info = True
                accepted = []
                window._a3_accept_source = accepted.append
                window._choose_basic_source()
                self.assertEqual(accepted, [extracted])
                self.assertNotIn('1525_006', self.message.question_text)

    def test_created_job_only_is_renamed_and_saved(self):
        window = self.cls.__new__(self.cls)
        api = types.SimpleNamespace(jobs=[types.SimpleNamespace(job_id='JOB-001', name='content')])
        api.workspace = lambda: api
        rename = []
        def rename_job(job_id, name):
            rename.append((job_id,name))
        api.rename_job = rename_job
        window.api = api
        window._stub_create = True
        window.basic_dias_label = types.SimpleNamespace(text=lambda: '1525_005 WebSak')
        saved = []
        window._v022_save_joblist_to_existing_file = lambda: saved.append(True) or True
        window._refresh = lambda **kwargs: None
        self.assertTrue(window._v022_register_current())
        self.assertEqual(rename, [('JOB-002','1525_005 WebSak')])
        self.assertEqual(len(saved), 1)
        window._stub_create = False
        self.assertTrue(window._v022_register_current())
        self.assertEqual(len(rename), 1)


if __name__ == '__main__':
    unittest.main()
