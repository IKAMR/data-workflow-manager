"""Regression tests for v0.1.8-a9 selective operations and durable history.

These tests are headless. They exercise the real selective API method from AST
without importing Qt or requiring external Noark/Arkade executables.
"""
from __future__ import annotations

import ast
import tempfile
import threading
import unittest
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

from app.run_log_history_v018_a8 import RunLogStore
from app.subjob_history_v018_a9 import run_history_lines

ROOT = Path(__file__).resolve().parents[1]


class ApiError(RuntimeError):
    pass


class Status(Enum):
    READY = "Klar"
    RUNNING = "Kjorer"
    WAITING = "Venter"
    OK = "Ferdig"
    FAILED = "Feil"


def load_selective_method():
    source = (ROOT / "app" / "subjob_execution_v018_a9.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    klass = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "SelectiveSubjobMixin")
    method = next(x for x in klass.body if isinstance(x, ast.FunctionDef) and x.name == "run_subjob")
    module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    namespace = {"DwmApiError": ApiError, "JobStatus": Status, "Path": Path,
                 "RunLogStore": RunLogStore}
    exec(compile(module, "subjob_execution_v018_a9.py", "exec"), namespace)
    return namespace["run_subjob"]


class FakeRunner:
    def __init__(self, facade, *, ok=True, fail=False):
        self.facade = facade
        self.ok = ok
        self.fail = fail

    def run_operation(self, job, operation_id, *, progress_cb, log_cb, cancelled_cb, state_cb):
        self.facade.executed.append(operation_id)
        job.status = Status.RUNNING
        job.progress = 0.5
        job.message = "Inside operation"
        job.next_operation_index = 6
        state_cb(job)
        log_cb("START: " + operation_id)
        progress_cb(0.45, "Running")
        if self.fail:
            raise RuntimeError("Simulated executor failure")
        log_cb(("OK: " if self.ok else "FEIL: ") + operation_id)
        job.status = Status.OK
        job.progress = 1.0
        job.next_operation_index = 9
        job.message = "Would corrupt parent without protection"
        return SimpleNamespace(ok=self.ok)


class Facade:
    run_subjob = load_selective_method()

    def __init__(self, root: Path):
        self.root = root
        self.work = root / "operations" / "dwm"
        self.work.mkdir(parents=True)
        self.settings = {"app_work_subfolder": "dwm"}
        self._guard = threading.Lock()
        self._running = False
        self._path = root / "jobs.n5jobs"
        self._cancel = threading.Event()
        self._active_job_id = "JOB-001"
        self._a8_run_writer = None
        self._a8_log_warning = ""
        self.job = SimpleNamespace(
            job_id="JOB-001", name="Archive", workflow_ids=["metadata_inventory", "arkade5_noark5_test"],
            status=Status.READY, progress=0.0, next_operation_index=0,
            message="unchanged", work_operations=self.work.parent,
        )
        self._batch = SimpleNamespace(jobs=lambda: [self.job])
        self.report = SimpleNamespace(errors=(), actions=(), warnings=())
        self.executed = []
        self.events = []
        self.ok = True
        self.fail = False
        self.storage_problems = ()
        self._runner_factory = lambda settings: FakeRunner(self, ok=self.ok, fail=self.fail)

    def _assert_idle(self):
        if self._running:
            raise ApiError("Another job is running")

    def _require_job(self, job_id):
        if job_id != self.job.job_id:
            raise ApiError("Unknown job")
        return self.job

    def preflight_subjob(self, job_id, operation_id):
        if operation_id not in self._require_job(job_id).workflow_ids:
            raise ApiError("Unknown operation")
        return self.report

    def check_storage(self):
        return self.storage_problems

    def _view(self, job, position):
        return SimpleNamespace(effective_work_operations=str(self.work), name=job.name)

    def _registry_catalog(self):
        return {"metadata_inventory": ("Metadataoversikt", "Metadata"),
                "arkade5_noark5_test": ("Arkade Noark5", "Analyse")}

    def _emit(self, kind, job=None, *, message="", progress=None):
        self.events.append((kind, message, progress))
        writer = self._a8_run_writer
        if writer is not None and kind in {"subjob.started", "subjob.log", "subjob.finished", "subjob.error"}:
            writer.append(message)


class SelectiveRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.facade = Facade(Path(self.tmp.name))

    def test_selected_operation_only(self):
        self.assertTrue(self.facade.run_subjob("JOB-001", "metadata_inventory"))
        self.assertEqual(self.facade.executed, ["metadata_inventory"])

    def test_parent_cursor_and_status_preserved(self):
        self.facade.run_subjob("JOB-001", "metadata_inventory")
        self.assertEqual((self.facade.job.status, self.facade.job.progress,
                          self.facade.job.next_operation_index, self.facade.job.message),
                         (Status.READY, 0.0, 0, "unchanged"))
        self.assertEqual(len(self.facade.job.workflow_ids), 2)

    def test_previous_execution_requires_explicit_consent(self):
        self.facade.job.next_operation_index = 1
        self.facade.job.status = Status.OK
        with self.assertRaises(ApiError):
            self.facade.run_subjob("JOB-001", "metadata_inventory")
        self.assertEqual(list(self.facade.work.iterdir()), [])

    def test_authorized_rerun_retains_parent_completion(self):
        self.facade.job.next_operation_index = 2
        self.facade.job.status = Status.OK
        self.facade.job.progress = 1.0
        self.assertTrue(self.facade.run_subjob("JOB-001", "metadata_inventory", allow_rerun=True))
        self.assertEqual((self.facade.job.status,self.facade.job.next_operation_index), (Status.OK,2))

    def test_waiting_job_cannot_be_selectively_run(self):
        self.facade.job.status = Status.WAITING
        with self.assertRaises(ApiError):
            self.facade.run_subjob("JOB-001", "metadata_inventory")

    def test_running_job_cannot_be_selectively_run(self):
        self.facade._running = True
        with self.assertRaises(ApiError):
            self.facade.run_subjob("JOB-001", "metadata_inventory")

    def test_unsaved_job_list_is_blocked(self):
        self.facade._path = None
        with self.assertRaises(ApiError):
            self.facade.run_subjob("JOB-001", "metadata_inventory")

    def test_missing_work_is_blocked(self):
        self.facade._view = lambda job,pos: SimpleNamespace(effective_work_operations=None, name=job.name)
        with self.assertRaises(ApiError):
            self.facade.run_subjob("JOB-001", "metadata_inventory")

    def test_work_conflict_is_blocked(self):
        self.facade.storage_problems = ("Conflicting Work directories",)
        with self.assertRaises(ApiError):
            self.facade.run_subjob("JOB-001", "metadata_inventory")

    def test_missing_dependency_blocks_before_log_created(self):
        self.facade.report = SimpleNamespace(errors=[SimpleNamespace(message="Missing Arkade CLI")],
                                             actions=(), warnings=())
        with self.assertRaises(ApiError):
            self.facade.run_subjob("JOB-001", "arkade5_noark5_test")
        self.assertFalse((self.facade.work / 'run_logs').exists())

    def test_missing_work_action_blocks_before_consent(self):
        self.facade.report = SimpleNamespace(errors=(), actions=[SimpleNamespace(path="new")], warnings=())
        with self.assertRaises(ApiError):
            self.facade.run_subjob("JOB-001", "metadata_inventory", acknowledge_warnings=True)

    def test_warnings_require_acknowledgement(self):
        self.facade.report = SimpleNamespace(errors=(), actions=(), warnings=[SimpleNamespace(message="Upstream results")])
        with self.assertRaises(ApiError):
            self.facade.run_subjob("JOB-001", "metadata_inventory")
        self.assertTrue(self.facade.run_subjob("JOB-001", "metadata_inventory", acknowledge_warnings=True))

    def test_error_creates_failed_log_and_recovers_idle(self):
        self.facade.fail = True
        with self.assertRaisesRegex(RuntimeError, "Simulated executor"):
            self.facade.run_subjob("JOB-001", "metadata_inventory")
        self.assertFalse(self.facade._running)
        self.assertEqual(self.facade.job.status, Status.READY)
        records = RunLogStore(self.facade.work, "JOB-001").list_runs()
        self.assertEqual(records[0].status, "failed")

    def test_success_log_is_durable_and_selective(self):
        self.facade.run_subjob("JOB-001", "metadata_inventory")
        store = RunLogStore(self.facade.work, "JOB-001")
        rec = store.list_runs()[0]
        self.assertEqual((rec.run_kind, rec.operation_id, rec.operation_name),
                         ("subjob", "metadata_inventory", "Metadataoversikt"))
        self.assertIn("START: metadata_inventory", store.read(rec.run_id))
        self.assertIn("DELJOBB RESULTAT: OK", store.read(rec.run_id))

    def test_failed_operation_log_status(self):
        self.facade.ok = False
        self.assertFalse(self.facade.run_subjob("JOB-001", "metadata_inventory"))
        self.assertEqual(RunLogStore(self.facade.work, "JOB-001").list_runs()[0].status, "failed")

    def test_effective_work_attribute_is_cleaned(self):
        self.facade.run_subjob("JOB-001", "metadata_inventory")
        self.assertFalse(hasattr(self.facade.job, "_effective_work_operations"))
        self.assertFalse(self.facade._running)

    def test_runner_receives_unique_run_id_in_settings(self):
        collected=[]
        def factory(settings):
            collected.append(settings.get("_current_run_id"))
            return FakeRunner(self.facade)
        self.facade._runner_factory=factory
        self.facade.run_subjob("JOB-001", "metadata_inventory")
        self.assertRegex(collected[0], r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
        self.assertNotIn("_current_run_id", self.facade.settings)


class HistoryTests(unittest.TestCase):
    def test_old_log_without_run_kind_is_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RunLogStore(Path(tmp), "JOB-002")
            writer = store.begin(job_name="old")
            writer.finish()
            info = store.list_runs()[0]
            self.assertEqual(info.run_kind, "workflow")
            self.assertEqual(info.operation_id, "")

    def test_subjob_timeline_is_distinct_from_parent_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RunLogStore(Path(tmp), "JOB-002")
            writer = store.begin(job_name="test", run_kind="subjob", operation_id="arkade5_noark5_test", operation_name="Arkade")
            writer.finish("finished")
            line = run_history_lines(store.list_runs())[0]
            self.assertIn("Deljobb: Arkade", line)
            self.assertIn("OK", line)
            self.assertNotIn("9/9", line)

    def test_invalid_operation_id_is_rejected_before_disk_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=RunLogStore(Path(tmp) / "w", "JOB-001")
            with self.assertRaises(ValueError):
                store.begin(job_name="x", run_kind="subjob", operation_id="../evil")
            self.assertFalse(store.base.exists())

    def test_log_lists_are_per_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=RunLogStore(Path(tmp), "JOB-001")
            b=RunLogStore(Path(tmp), "JOB-002")
            writer=a.begin(job_name="One", run_kind="subjob",operation_id="metadata_inventory")
            writer.finish()
            self.assertEqual(len(a.list_runs()),1)
            self.assertEqual(len(b.list_runs()),0)

    def test_empty_history_is_labeled(self):
        self.assertIn("Ingen separate",run_history_lines(())[0])


class GuiContractTests(unittest.TestCase):
    def test_qt_has_selected_subjob_actions_and_docks(self):
        source=(ROOT/'gui_qt'/'main_window.py').read_text(encoding='utf-8')
        ast.parse(source)
        for name in ('_a9_workflow_context_menu','_a9_run_selected_subjob','_a9_start_subjob_worker',
                     'run_history_lines(', 'self.api.run_subjob(', 'self.api.preflight_subjob(',
                     'self.api.run_job(', 'self._dock("log"', 'self._dock("run"'):
            self.assertIn(name,source)
        self.assertNotIn('from gui.persistent_app',source)

    def test_backend_preflight_is_operation_specific(self):
        source=(ROOT/'app'/'workbench_api_v018_a3.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('inspection_job = replace(job, workflow_ids=[operation_id])', source)
        self.assertIn('operation_id=operation_id', source)
        self.assertIn('SelectiveSubjobMixin', source)


if __name__ == '__main__':
    unittest.main()

class UiRuntimeRoutingTests(unittest.TestCase):
    """Exercise actual Qt handler functions with fake widgets (no PySide6)."""

    @staticmethod
    def ui_methods(*names):
        source=(ROOT/'gui_qt'/'main_window.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        klass=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='DwmMainWindow')
        funcs=[node for node in klass.body if isinstance(node,ast.FunctionDef) and node.name in names]
        assert len(funcs)==len(names)
        class FakeQt:
            class ItemDataRole:
                UserRole=21
        class FakeBox:
            class StandardButton:
                Yes=1
                No=2
            def information(self,*args,**kwargs):pass
            def warning(self,*args,**kwargs):pass
            def question(self,*args,**kwargs):return 1
        namespace={'Qt':FakeQt,'QMessageBox':FakeBox(),
                   'Queue':__import__('queue').Queue,'Thread':threading.Thread}
        exec(compile(ast.fix_missing_locations(ast.Module(body=funcs,type_ignores=[])),
                     'gui_qt/main_window.py','exec'),namespace)
        return type('Actions',(),{name:namespace[name] for name in names})

    def test_selected_operation_id_is_resolved_from_current_row(self):
        base=self.ui_methods('_a9_selected_operation_id')
        row=SimpleNamespace(data=lambda col,role:'metadata_inventory')
        fake=base()
        fake.workflow_tree=SimpleNamespace(currentItem=lambda:row)
        self.assertEqual(fake._a9_selected_operation_id(),'metadata_inventory')
        fake.workflow_tree=SimpleNamespace(currentItem=lambda:None)
        self.assertIsNone(fake._a9_selected_operation_id())

    def test_button_routes_only_selected_operation_to_worker(self):
        base=self.ui_methods('_a9_run_selected_subjob')
        fake=base()
        fake._active_id='JOB-001'
        fake._worker=None
        fake.api=SimpleNamespace(running=False, job_details=lambda _id:SimpleNamespace(
            job=SimpleNamespace(status='Klar'),
            operations=(SimpleNamespace(operation_id='metadata_inventory',completed=False,name='Metadata'),)))
        fake._a9_selected_operation_id=lambda:'metadata_inventory'
        received=[]
        fake._a9_start_subjob_worker=lambda *args:received.append(args)
        fake._a9_run_selected_subjob()
        self.assertEqual(received,[('JOB-001','metadata_inventory',False)])

    def test_single_operation_worker_calls_selective_api_not_whole_job(self):
        base=self.ui_methods('_a9_start_subjob_worker')
        fake=base()
        fake.api=SimpleNamespace(
            workspace=lambda:SimpleNamespace(job_list_path='A.n5jobs'),dirty=False,
            check_storage=lambda:(),run_subjob=lambda *args,**kwargs:received.append((args,kwargs)) or True)
        fake._review_preflight=lambda jobs,**kwargs:{'JOB-001'}
        fake._save=lambda:True
        fake._set_running_ui=lambda running:None
        fake._append_log=lambda msg:None
        fake._batch_stop=threading.Event()
        received=[]
        fake._a9_start_subjob_worker('JOB-001','metadata_inventory',False)
        fake._worker.join(timeout=2)
        self.assertFalse(fake._worker.is_alive())
        self.assertEqual(received[0][0],('JOB-001','metadata_inventory'))
        self.assertTrue(received[0][1]['acknowledge_warnings'])
        self.assertFalse(received[0][1]['allow_rerun'])
        self.assertIn(('done','Deljobb metadata_inventory: kj\u00f8ringen er avsluttet.'),
                      list(fake._worker_messages.queue))

    def test_subjob_progress_updates_run_view_not_parent_status(self):
        base=self.ui_methods('_a9_process_subjob_event')
        fake=base()
        fake._active_id='JOB-001'
        fake.run_summary=SimpleNamespace(setText=lambda text: summaries.append(text))
        fake.run_progress_bar=SimpleNamespace(setValue=lambda value:values.append(value))
        fake.run_events=SimpleNamespace(clear=lambda:None, appendPlainText=lambda text:None)
        fake.auto_show_log_action=SimpleNamespace(isChecked=lambda:False)
        fake._a9_sync_detached_run=lambda:None
        summaries=[];values=[]
        fake._a9_process_subjob_event(SimpleNamespace(job_id='JOB-001',kind='subjob.started',message='Metadata',progress=0))
        fake._a9_process_subjob_event(SimpleNamespace(job_id='JOB-001',kind='subjob.progress',message='Halfway',progress=0.5))
        self.assertEqual(values[-1],50)
        self.assertIn('Halfway',summaries[-1])


class OperationPreflightIsolationTests(unittest.TestCase):
    @staticmethod
    def check_for(operation_id):
        from dataclasses import dataclass, replace
        source = (ROOT / 'app' / 'workbench_api_v018_a3.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        klass = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'DwmWorkbenchAPI')
        method = next(x for x in klass.body if isinstance(x, ast.FunctionDef) and x.name == '_inspect_job')

        @dataclass(frozen=True)
        class Job:
            job_id: str = 'JOB-001'
            workflow_ids: tuple[str, ...] = ('metadata_inventory', 'arkade5_noark5_test', 'dias_package')
            work_operations: Path = Path('/tmp/work/operations')
            work_root: Path | None = None

        @dataclass(frozen=True)
        class Report:
            job_id: str
            issues: tuple
            actions: tuple

        @dataclass(frozen=True)
        class Issue:
            code: str
            level: str
            message: str

        class Checker:
            def __init__(self): self.calls = 0
            def check(self, settings):
                self.calls += 1
                return SimpleNamespace(severity='error', message='Missing Arkade CLI')

        job = Job()
        checker = Checker()
        def fake_inspect(projection, *, effective_work_operations, app_subfolder):
            return Report(projection.job_id, (), ())
        namespace = {
            'replace': replace, 'DwmApiError': ApiError, 'inspect_job': fake_inspect,
            'requires_arkade_cli': lambda ids: 'arkade5_noark5_test' in ids,
            'PreflightReport': Report, 'PreflightIssue': Issue,
            'effective_work_operations': lambda base, app, rule, job, position: base / app,
        }
        code = ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[]))
        exec(compile(code,'workbench_api_v018_a3.py','exec'), namespace)
        fake = SimpleNamespace(settings={'app_work_subfolder':'dwm'},
                               _batch=SimpleNamespace(jobs=lambda:[job]),
                               _arkade_checker=checker)
        fake.output_subfolder_rule = ''
        report = namespace['_inspect_job'](fake,job,operation_id=operation_id)
        return report, checker.calls

    def test_unrelated_arkade_cli_does_not_block_metadata(self):
        report, calls = self.check_for('metadata_inventory')
        self.assertEqual(calls,0)
        self.assertEqual(report.issues,())

    def test_actual_arkade_operation_checks_its_cli(self):
        report, calls = self.check_for('arkade5_noark5_test')
        self.assertEqual(calls,1)
        self.assertEqual(report.issues[0].level,'error')
        self.assertIn('Missing Arkade CLI',report.issues[0].message)

    def test_dias_packaging_requires_explicit_upstream_warning(self):
        report, calls = self.check_for('dias_package')
        self.assertEqual(calls,0)
        self.assertEqual(report.issues[0].level,'warning')
        self.assertIn('SUBJOB_REQUIRES_RESULTS',report.issues[0].code)
