"""a1.3: Direct selected Work, stable legacy paths, persistent Job marker.

Qt-free, with the actual source methods executed through AST to keep this
regression runnable in both full DWM and small release-delta verification.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'app' / 'work_output_layout.py'
API = ROOT / 'app' / 'workbench_api_v0111_a1.py'
BASIC = ROOT / 'app' / 'basic_start_v0111_a1.py'
GUI = ROOT / 'gui_qt' / 'basic_main_v0111_a1.py'


def load_output_functions():
    source = ast.parse(OUTPUT.read_text(encoding='utf-8'))
    wanted = {'AppWorkSubfolderError', 'validate_app_work_subfolder',
              'uses_direct_work_folder', 'effective_work_operations', 'validate_layout'}
    nodes = [node for node in source.body
             if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted]
    ns = {'Path': Path, 'DWM_WORK_LAYOUT_PARAM': '__dwm_work_layout__',
          '_INVALID_COMPONENT': re.compile(r'[<>:"/\\|?*\x00-\x1f]'),
          'render_output_subfolder_rule': lambda rule, _job, _position: 'JOB-001' if rule else ''}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(OUTPUT), 'exec'), ns)
    return ns


class DirectWorkLayoutTests(unittest.TestCase):
    def setUp(self):
        self.api = load_output_functions()

    def make_job(self, directory, *, mode=None, job_id='JOB-001'):
        params = {'__dwm_work_layout__': {'mode': mode}} if mode else {}
        return SimpleNamespace(job_id=job_id, work_operations=directory, operation_params=params)

    def test_direct_work_equals_exactly_user_selected_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected = Path(tmp) / 'a01'
            selected.mkdir()
            job = self.make_job(selected, mode='selected')
            actual = self.api['effective_work_operations'](selected, 'dwm', '{JOB}', job, 1)
            self.assertEqual(actual, selected)
            self.assertEqual(list(selected.iterdir()), [])

    def test_existing_advanced_jobs_keep_app_and_job_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected = Path(tmp) / 'a01'
            job = self.make_job(selected)
            self.assertEqual(
                self.api['effective_work_operations'](selected, 'dwm', '{JOB}', job, 1),
                selected / 'dwm' / 'JOB-001',
            )

    def test_work_layout_marker_roundtrips_json_without_global_settings(self):
        job = self.make_job(Path('/example/work'), mode='selected')
        payload = json.loads(json.dumps({'operation_params': job.operation_params}))
        restored = self.make_job(job.work_operations)
        restored.operation_params = payload['operation_params']
        self.assertTrue(self.api['uses_direct_work_folder'](restored))
        self.assertEqual(self.api['effective_work_operations'](
            restored.work_operations, 'other-global-folder', 'job-rule', restored, 1,
        ), restored.work_operations)
        self.assertFalse(self.api['uses_direct_work_folder'](self.make_job(Path('/example/work'))))

    def test_multiple_direct_jobs_cannot_share_one_work_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            jobs = [self.make_job(path, mode='selected', job_id='JOB-A'),
                    self.make_job(path, mode='selected', job_id='JOB-B')]
            with self.assertRaisesRegex(ValueError, 'samme Work-output'):
                self.api['validate_layout']('dwm', '{JOB}', jobs)

    def test_no_changes_to_physical_work_path_until_control(self):
        source = BASIC.read_text(encoding='utf-8')
        self.assertNotIn('propose_profile_work_location(', source)
        self.assertIn('work_operations=chosen', source)
        self.assertIn('api.use_selected_work_directly(view.job_id)', source)
        self.assertNotIn('.mkdir(', source)
        self.assertNotIn('shutil.copy', source)


class PublicApiBridgeTests(unittest.TestCase):
    def create_api_double(self, work, *, existing_refs=None, others=None):
        source = ast.parse(API.read_text(encoding='utf-8'))
        cls = next(n for n in source.body if isinstance(n, ast.ClassDef)
                   and n.name == 'DwmWorkbenchAPI')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'use_selected_work_directly')
        ns = {'Path': Path, 'DwmApiError': ValueError,
              'DWM_WORK_LAYOUT_PARAM': '__dwm_work_layout__',
              'effective_work_operations': lambda path, app, rule, job, index: path}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                     str(API), 'exec'), ns)

        job = SimpleNamespace(job_id='JOB-NEW', source_extraction=work.parent / 'source',
                              work_operations=work, work_root=work, operation_params={})
        def set_params(name, params): job.operation_params[name] = dict(params)
        job.set_operation_params = set_params
        members = [job] + list(others or [])
        state = SimpleNamespace(
            _guard=threading.RLock(), _assert_idle=lambda: None,
            _require_job=lambda _id: job, _work_references=existing_refs or {},
            _batch=SimpleNamespace(jobs=lambda: members),
            settings={'app_work_subfolder': 'dwm'}, output_subfolder_rule='{JOB}',
            _dirty=False, _emit=lambda *_args, **_kwargs: None,
            use_selected_work_directly=ns['use_selected_work_directly'],
        )
        return state, job

    def test_api_marks_unprovisioned_basic_job_as_direct(self):
        with tempfile.TemporaryDirectory() as tmp:
            chosen = Path(tmp) / 'a01'
            chosen.mkdir()
            state, job = self.create_api_double(chosen)
            state.use_selected_work_directly(state, job.job_id)
            self.assertEqual(job.operation_params['__dwm_work_layout__'], {'mode': 'selected'})
            self.assertTrue(state._dirty)

    def test_api_does_not_repurpose_existing_work_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            chosen = Path(tmp) / 'a01'
            chosen.mkdir()
            (chosen / 'job.json').write_text('{}', encoding='utf-8')
            state, job = self.create_api_double(chosen)
            with self.assertRaisesRegex(ValueError, 'job.json'):
                state.use_selected_work_directly(state, job.job_id)
            self.assertEqual(job.operation_params, {})

    def test_api_rejects_already_registered_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            chosen = Path(tmp) / 'a01'
            chosen.mkdir()
            state, job = self.create_api_double(
                chosen, existing_refs={'JOB-NEW': chosen / 'job.json'},
            )
            with self.assertRaisesRegex(ValueError, 'historikk'):
                state.use_selected_work_directly(state, job.job_id)

    def test_gui_does_not_hide_existing_legacy_work_folder(self):
        source = GUI.read_text(encoding='utf-8')
        self.assertIn('self._basic_legacy_layout = bool(', source)
        self.assertIn('Eksisterende jobb bruker avansert Work-struktur:', source)
        self.assertIn('not getattr(self, \'_basic_legacy_layout\', False)', source)
        self.assertIn('Work brukes direkte:', source)


if __name__ == '__main__':
    unittest.main()
