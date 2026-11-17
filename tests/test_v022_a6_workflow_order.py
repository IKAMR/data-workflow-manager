"""a6: per-job operation order, Basic/Advanced persistence and safety contracts."""
from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import tomllib

from app.workflow_order_v022_a6 import (
    ARKADE_NOARK5, ARKADE_PRONOM, arkade_last_order,
    checked_order, move_operation, ordering_warnings, preserved_basic_order,
)
from app.basic_multijob_v022_a1_2 import register_basic_plan
from app.basic_start_v0111_a1 import existing_basic_job

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = (
    'metadata_inventory', 'validate_xml_schema', 'analyse_arkivstruktur',
    'run_noark5_xpath_tests_2026', ARKADE_NOARK5,
    'siegfried_pronom_identification', ARKADE_PRONOM,
    'import_arkade5_reports', 'compose_noark5_views', 'build_noark5_depot_report',
)


class OrderingModelTests(unittest.TestCase):
    def test_arkade_preset_puts_noark5_second_last_pronom_last(self):
        result = arkade_last_order(EXAMPLE)
        self.assertEqual(result[-2:], (ARKADE_NOARK5, ARKADE_PRONOM))
        self.assertEqual(result[:-2], tuple(i for i in EXAMPLE if i not in
                                             (ARKADE_NOARK5, ARKADE_PRONOM)))
        self.assertEqual(arkade_last_order(result), result)

    def test_preset_retains_missing_arkade_operation(self):
        only_pronom = ('a', ARKADE_PRONOM, 'b')
        self.assertEqual(arkade_last_order(only_pronom), ('a', 'b', ARKADE_PRONOM))
        self.assertEqual(arkade_last_order(('a', 'b')), ('a', 'b'))

    def test_manual_move_up_and_down_is_stable(self):
        self.assertEqual(move_operation(('a', 'b', 'c'), 2, -1), ('a', 'c', 'b'))
        self.assertEqual(move_operation(('a', 'b', 'c'), 0, 1), ('b', 'a', 'c'))
        self.assertEqual(move_operation(('a', 'b', 'c'), 0, -1), ('a', 'b', 'c'))
        self.assertEqual(move_operation(('a', 'b', 'c'), 2, 1), ('a', 'b', 'c'))

    def test_reject_added_removed_or_duplicate_operations(self):
        for value in (('a',), ('a', 'b', 'x'), ('a', 'a'), ('b', 'b'), ()):
            with self.subTest(value=value), self.assertRaises(ValueError):
                checked_order(('a', 'b'), value)
        with self.assertRaises(ValueError):
            checked_order(('a', 'a'), ('a', 'a'))
        with self.assertRaises(ValueError):
            move_operation(('a', 'b'), 0, 2)

    def test_basic_re_registration_keeps_only_custom_order_not_membership(self):
        basic = ('a', 'b', 'c')
        self.assertEqual(preserved_basic_order(('c', 'a', 'b'), basic), ('c', 'a', 'b'))
        self.assertEqual(preserved_basic_order(('c', 'a'), basic), basic)
        self.assertEqual(preserved_basic_order(('b', 'a', 'd'), basic), basic)

    def test_report_is_marked_stale_when_arkade_is_last(self):
        warnings = ordering_warnings(arkade_last_order(EXAMPLE))
        self.assertTrue(any('import' in text.casefold() for text in warnings))
        self.assertTrue(any('rapport' in text.casefold() for text in warnings))
        self.assertFalse(ordering_warnings(('metadata_inventory', ARKADE_NOARK5,
                                             ARKADE_PRONOM, 'import_arkade5_reports',
                                             'build_noark5_depot_report')))

    def test_dependent_operations_wrong_order_is_reported(self):
        warnings = ordering_warnings(('build_noark5_depot_report',
                                     'compose_noark5_views',
                                     'run_noark5_xpath_tests_2026'))
        self.assertEqual(len(warnings), 2)


@dataclass
class FakeJob:
    job_id: str
    source_extraction: Path
    work_root: Path
    work_operations: Path
    effective_work_operations: Path
    operation_ids: tuple[str, ...]
    name: str = 'content'
    status: str = 'Klar'
    current_operation: int = 0


class FakeApi:
    def __init__(self, jobs):
        self.jobs = list(jobs)
        self.selected = self.jobs[0].job_id
        self.changed = []
        self.running = False
        self.job_list_path = None

    def workspace(self):
        return SimpleNamespace(jobs=tuple(self.jobs), job_list_path=self.job_list_path)

    def job_details(self, job_id):
        job = next(j for j in self.jobs if j.job_id == job_id)
        ops = tuple(SimpleNamespace(operation_id=op, name=op) for op in job.operation_ids)
        return SimpleNamespace(job=job, operations=ops)

    def set_workflow(self, job_id, ids):
        job = self.job_details(job_id).job
        job.operation_ids = tuple(ids)
        self.changed.append((job_id, tuple(ids)))

    def select_job(self, job_id):
        self.selected = job_id

    def save_job_list(self, path=None):
        if path is not None:
            self.job_list_path = Path(path)
        payload = {j.job_id: list(j.operation_ids) for j in self.jobs}
        self.job_list_path.write_text(json.dumps(payload), encoding='utf-8')
        return self.job_list_path


class SameJobPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.jobs = [FakeJob(f'JOB-{i:03d}', root / f'source_{i}', root / f'work_{i}',
                             root / f'work_{i}', root / f'work_{i}', EXAMPLE)
                     for i in range(1, 4)]
        self.api = FakeApi(self.jobs)
        self.plan = SimpleNamespace(source_extraction=self.jobs[1].source_extraction,
                                    work_root=self.jobs[1].work_root,
                                    work_operations=self.jobs[1].work_operations,
                                    operation_ids=EXAMPLE)

    def test_basic_save_and_start_never_overwrite_selected_order(self):
        wanted = arkade_last_order(EXAMPLE)
        self.api.set_workflow('JOB-002', wanted)
        self.api.changed.clear()
        for _ in range(3):
            result = register_basic_plan(self.api, self.plan,
                                         selected_job_id='JOB-002')
            self.assertFalse(result.workflow_changed)
            self.assertEqual(self.jobs[1].operation_ids, wanted)
        self.assertEqual(self.api.changed, [])
        self.assertEqual(existing_basic_job(self.api, self.plan), 'JOB-002')
        self.assertEqual(self.jobs[0].operation_ids, EXAMPLE)
        self.assertEqual(self.jobs[2].operation_ids, EXAMPLE)

    def test_basic_checkbox_membership_change_recomposes_only_active_job(self):
        self.api.set_workflow('JOB-002', arkade_last_order(EXAMPLE))
        self.api.changed.clear()
        other_plan = SimpleNamespace(**{**vars(self.plan),
                                       'operation_ids': tuple(x for x in EXAMPLE if x != ARKADE_PRONOM)})
        result = register_basic_plan(self.api, other_plan, selected_job_id='JOB-002')
        self.assertTrue(result.workflow_changed)
        self.assertEqual(self.jobs[1].operation_ids, other_plan.operation_ids)
        self.assertEqual(self.jobs[0].operation_ids, EXAMPLE)
        self.assertEqual(self.jobs[2].operation_ids, EXAMPLE)

    def test_basic_rejects_different_control_membership_for_old_work(self):
        self.api.set_workflow('JOB-002', tuple(x for x in EXAMPLE if x != ARKADE_PRONOM))
        with self.assertRaisesRegex(ValueError, 'annen arbeidsflyt'):
            existing_basic_job(self.api, self.plan)

    def test_saved_joblist_round_trip_keeps_each_jobs_order(self):
        with tempfile.TemporaryDirectory() as temp:
            self.api.set_workflow('JOB-002', arkade_last_order(EXAMPLE))
            path = Path(temp) / 'jobs.n5jobs'
            self.api.save_job_list(path)
            saved = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(tuple(saved['JOB-002']), arkade_last_order(EXAMPLE))
            self.assertEqual(tuple(saved['JOB-001']), EXAMPLE)
            self.assertEqual(tuple(saved['JOB-003']), EXAMPLE)


class VersionAndIntegrationContracts(unittest.TestCase):
    def test_version_and_distribution_are_both_a6(self):
        from version import APP_NAME, VERSION
        self.assertEqual(APP_NAME, 'Data Workflow Manager')
        from tests.version_assertions import assert_release_at_least
        assert_release_at_least(self, f'VERSION = "{VERSION}"', '0.2.2', 6)
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            self.assertEqual(tomllib.load(stream)['project']['version'], VERSION.replace('-a', 'a'))

    def test_both_modes_install_same_editor_with_lazy_import(self):
        main = (ROOT / 'gui_qt/main_v020_a6.py').read_text(encoding='utf-8')
        self.assertIn('self._a6_install_workflow_order()', main)
        self.assertIn('self.a6_order_action', main)
        self.assertIn('self.a6_basic_order_button', main)
        self.assertIn('self.a6_workflow_order_button', main)
        self.assertIn('from gui_qt.workflow_order_v022_a6 import open_active_job_order', main)
        self.assertIn('layout.insertWidget', main)
        # The actual UI module is only imported after a user opens the editor.
        self.assertNotIn('from gui_qt.workflow_order_v022_a6 import', main.split('class DwmMainWindow')[0])

    def test_dialog_uses_existing_api_and_blocks_ongoing_runs(self):
        ui = (ROOT / 'gui_qt/workflow_order_v022_a6.py').read_text(encoding='utf-8')
        self.assertIn('window.api.set_workflow(job_id, changed)', ui)
        self.assertIn('window.api.save_job_list()', ui)
        self.assertIn('window._worker is not None or window.api.running', ui)
        self.assertIn('QMessageBox.StandardButton.No', ui)
        self.assertNotIn('unlink(', ui)
        self.assertNotIn('rmtree(', ui)

    def test_gui_handler_refuses_busy_job_without_mutation(self):
        ui_path = ROOT / 'gui_qt/workflow_order_v022_a6.py'
        spec = importlib.util.spec_from_file_location('a6_order_gui_headless', ui_path)
        self.assertIsNotNone(spec)
        core = ModuleType('PySide6.QtCore')
        core.Qt = SimpleNamespace()
        widgets = ModuleType('PySide6.QtWidgets')
        class DummyDialog:
            class DialogCode:
                Accepted = 1
        class FakeMessage:
            calls = []
            @classmethod
            def information(cls, *args):
                cls.calls.append(args)
        widgets.QDialog = DummyDialog
        widgets.QDialogButtonBox = type('QDialogButtonBox', (), {})
        for name in ('QHBoxLayout', 'QLabel', 'QListWidget', 'QListWidgetItem',
                     'QPushButton', 'QVBoxLayout'):
            setattr(widgets, name, type(name, (), {}))
        widgets.QMessageBox = FakeMessage
        with patch.dict(sys.modules, {'PySide6': ModuleType('PySide6'),
                                      'PySide6.QtCore': core, 'PySide6.QtWidgets': widgets}):
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            fake = SimpleNamespace(_worker=object(), api=SimpleNamespace(running=False))
            self.assertFalse(mod.open_active_job_order(fake))
            self.assertEqual(len(FakeMessage.calls), 1)


    def test_gui_handler_persists_only_selected_job(self):
        ui_path = ROOT / 'gui_qt/workflow_order_v022_a6.py'
        spec = importlib.util.spec_from_file_location('a6_order_gui_save', ui_path)
        core = ModuleType('PySide6.QtCore')
        core.Qt = SimpleNamespace()
        widgets = ModuleType('PySide6.QtWidgets')
        class DummyDialog:
            class DialogCode:
                Accepted = 1
        class Message:
            class StandardButton:
                Yes = 1
                No = 2
            questions = []
            @classmethod
            def question(cls, *args):
                cls.questions.append(args)
                return cls.StandardButton.Yes
            @classmethod
            def warning(cls, *args):
                raise AssertionError('Unexpected warning ' + str(args))
            @classmethod
            def information(cls, *args):
                raise AssertionError('Unexpected information ' + str(args))
        widgets.QDialog = DummyDialog
        widgets.QDialogButtonBox = type('QDialogButtonBox', (), {})
        for name in ('QHBoxLayout', 'QLabel', 'QListWidget', 'QListWidgetItem',
                     'QPushButton', 'QVBoxLayout'):
            setattr(widgets, name, type(name, (), {}))
        widgets.QMessageBox = Message
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            jobs = [FakeJob('JOB-001', base/'source1', base/'work1', base/'work1',
                            base/'work1', EXAMPLE),
                    FakeJob('JOB-002', base/'source2', base/'work2', base/'work2',
                            base/'work2', EXAMPLE)]
            api = FakeApi(jobs)
            api.save_job_list(base/'multijob.n5jobs')
            class Window:
                def __init__(self):
                    self.api = api
                    self._worker = None
                    self._active_id = 'JOB-002'
                    self._basic_active = False
                    self._render_key = object()
                    self.refreshed = []
                def _remember_joblist(self, path):
                    self.remembered = path
                def _refresh(self, **kwargs):
                    self.refreshed.append(kwargs)
                def statusBar(self):
                    return SimpleNamespace(showMessage=lambda *args: None)
            window = Window()
            with patch.dict(sys.modules, {'PySide6': ModuleType('PySide6'),
                                          'PySide6.QtCore': core, 'PySide6.QtWidgets': widgets}):
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                class FakeDialog:
                    def __init__(self, *args, **kwargs):
                        self._original = tuple(op.operation_id for op in kwargs['operations'])
                    def exec(self):
                        return 1
                    def operation_ids(self):
                        return __import__("app.workflow_dependencies_v022_a7", fromlist=["arkade_last_with_dependencies"]).arkade_last_with_dependencies(self._original)
                module.WorkflowOrderDialog = FakeDialog
                self.assertTrue(module.open_active_job_order(window))
            self.assertEqual(tuple(jobs[1].operation_ids), __import__('app.workflow_dependencies_v022_a7', fromlist=['arkade_last_with_dependencies']).arkade_last_with_dependencies(EXAMPLE))
            self.assertEqual(tuple(jobs[0].operation_ids), EXAMPLE)
            saved = json.loads((base/'multijob.n5jobs').read_text(encoding='utf-8'))
            self.assertEqual(tuple(saved['JOB-002']), __import__('app.workflow_dependencies_v022_a7', fromlist=['arkade_last_with_dependencies']).arkade_last_with_dependencies(EXAMPLE))
            self.assertEqual(tuple(saved['JOB-001']), EXAMPLE)
            self.assertEqual(window.refreshed, [{'force': True}])
            self.assertFalse(Message.questions)  # Ready, not previously run.


if __name__ == '__main__':
    unittest.main()
