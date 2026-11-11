"""a2.3: Arkade Noark and PRONOM must use the same persisted Basic Work."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORK_PATHS = ROOT / 'noark5_workflow' / 'core' / 'work_paths.py'
ARKADE_OPERATION = ROOT / 'noark5_workflow' / 'operations' / 'run_arkade5_cli.py'


def load_paths():
    spec = importlib.util.spec_from_file_location('direct_work_path_under_test', WORK_PATHS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_job(path: Path, *, direct: bool, document: bool = True):
    path.mkdir(parents=True, exist_ok=True)
    job = {'operation_params': {
        '__dwm_work_layout__': {'mode': 'selected'} if direct else {'mode': 'legacy'}
    }}
    payload = {'file_type': 'dwm-work-job', 'format_version': 1, 'job': job}
    (path / 'job.json').write_text(json.dumps(payload), encoding='utf-8')


class WorkPathContract(unittest.TestCase):
    def test_direct_basic_work_is_not_wrapped_in_dwm(self):
        mod = load_paths()
        with tempfile.TemporaryDirectory() as temp:
            selected = Path(temp) / 'a01'
            write_job(selected, direct=True)
            cfg = {'app_work_subfolder': 'dwm'}
            self.assertEqual(mod.resolve_dwm_work_root(selected, settings=cfg), selected)
            self.assertEqual(mod.resolve_work_operations_base(selected, settings=cfg), selected)
            self.assertEqual(mod.resolve_dwm_path(selected, 'external_evidence', settings=cfg),
                             selected / 'external_evidence')
            self.assertEqual(mod.resolve_dwm_path(selected, 'external_runs', settings=cfg),
                             selected / 'external_runs')

    def test_legacy_and_unmarked_work_still_use_dwm(self):
        mod = load_paths()
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'a01'
            base.mkdir()
            cfg = {'app_work_subfolder': 'dwm'}
            self.assertEqual(mod.resolve_dwm_work_root(base, settings=cfg), base / 'dwm')
            write_job(base, direct=False)
            self.assertEqual(mod.resolve_dwm_work_root(base, settings=cfg), base / 'dwm')
            self.assertEqual(mod.resolve_dwm_work_root(base / 'dwm', settings=cfg), base / 'dwm')
            self.assertEqual(mod.resolve_dwm_work_root(base / 'dwm' / 'JOB-001', settings=cfg),
                             base / 'dwm' / 'JOB-001')

    def test_malformed_untrusted_or_forged_marker_does_not_opt_in(self):
        mod = load_paths()
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config = {'app_work_subfolder': 'dwm'}
            for payload in ({}, {'job': {'operation_params': {
                '__dwm_work_layout__': {'mode': 'selected'}}}},
                {'file_type': 'dwm-work-job', 'job': []},
                {'file_type': 'dwm-work-job', 'job': {'operation_params': {
                    '__dwm_work_layout__': {'mode': 'other'}}}}):
                (base / 'job.json').write_text(json.dumps(payload), encoding='utf-8')
                with self.subTest(payload=payload):
                    self.assertEqual(mod.resolve_dwm_work_root(base, settings=config), base / 'dwm')
            (base / 'job.json').write_text('{ broken', encoding='utf-8')
            self.assertEqual(mod.resolve_dwm_work_root(base, settings=config), base / 'dwm')

    def test_no_io_side_effects_from_root_resolution(self):
        mod = load_paths()
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'a01'
            write_job(base, direct=True)
            before = [(p.name, p.stat().st_size) for p in base.iterdir()]
            mod.resolve_dwm_work_root(base, settings={'app_work_subfolder': 'dwm'})
            self.assertEqual(before, [(p.name, p.stat().st_size) for p in base.iterdir()])


class ArkadeResultContract(unittest.TestCase):
    def run_fake(self, *, operation: str, attached: int, import_errors: int = 0):
        source = ast.parse(ARKADE_OPERATION.read_text(encoding='utf-8'))
        cls = next(node for node in source.body if isinstance(node, ast.ClassDef)
                   and node.name == '_Arkade5WorkflowOperation')
        methods = [node for node in cls.body if isinstance(node, ast.FunctionDef)]
        cls = ast.ClassDef(name='ArkadeOperationTest', bases=[], keywords=[], body=methods,
                           decorator_list=[])
        progress = []
        logs = []
        class Result:
            def __init__(self, ok, message, **kwargs):
                self.ok=ok;self.message=message
                self.data=kwargs.get('data',{})
                self.warnings=kwargs.get('warnings',[])
        result_data = SimpleNamespace(
            imported=1, already_imported=0, failed=import_errors,
            pronom_failed=0, pronom_attached=attached, pronom_unattached=1-attached,
            items=[SimpleNamespace(message='Fant ingen PRONOM-statistikkfil')]
        )
        context = SimpleNamespace(
            work_operations=Path('/work/direct'), extraction_root=Path('/source'),
            settings={'arkade5_cli_path':'/arkade'}, metadata={'job_id':'JOB-001'},
            progress=lambda fraction, message: progress.append((fraction,message)),
            log=logs.append, cancelled=lambda:False,
        )
        ns={
            'SimpleNamespace':SimpleNamespace,
            'OperationResult':Result,
            'ARKADE5_NOARK5':'noark5_test',
            'ARKADE5_PRONOM':'pronom_analysis',
            'build_arkade5_plan':lambda *_args,**_kw:[SimpleNamespace(output_dir=Path('/work/direct/pronom'))],
            'run_arkade5_plan':lambda *_args,**_kw:SimpleNamespace(runs=[SimpleNamespace(
                ok=True, plan=SimpleNamespace(output_dir=Path('/work/direct/pronom')))]),
            'import_arkade5_run_outputs':lambda *_args,**_kw:result_data,
        }
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                     str(ARKADE_OPERATION),'exec'),ns)
        obj=ns['ArkadeOperationTest']()
        obj.arkade_operation=operation
        obj.definition=SimpleNamespace(name='Arkade 5 - PRONOM')
        return obj.run(context),logs

    def test_pronom_without_statistics_is_not_a_success(self):
        result, logs = self.run_fake(operation='pronom_analysis', attached=0)
        self.assertFalse(result.ok)
        self.assertTrue(result.data['pronom_statistics_missing'])
        self.assertIn('PRONOM-evidens mangler',result.message)
        self.assertTrue(any('filformatinfo-statistikk' in line for line in logs))

    def test_pronom_with_attached_statistics_is_success(self):
        result,_=self.run_fake(operation='pronom_analysis',attached=1)
        self.assertTrue(result.ok)
        self.assertFalse(result.data['pronom_statistics_missing'])

    def test_noark5_success_does_not_require_pronom(self):
        result,_=self.run_fake(operation='noark5_test',attached=0)
        self.assertTrue(result.ok)

    def test_real_importer_uses_canonical_work_root(self):
        # This regression keeps the bridging contract explicit for the
        # existing Arkade 5 and PRONOM auto-import paths.
        code=ARKADE_OPERATION.read_text(encoding='utf-8')
        self.assertIn('import_arkade5_run_outputs', code)
        self.assertIn('build_arkade5_plan', code)
        self.assertNotIn('shutil.rmtree', code)

if __name__ == '__main__':
    unittest.main()
