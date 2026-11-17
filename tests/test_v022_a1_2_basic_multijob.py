"""v0.2.2-a1.2: shared Basic/Advanced job-list regression without Qt."""
from __future__ import annotations

import ast
from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from app.basic_multijob_v022_a1_2 import (
    list_job_labels, register_basic_plan, same_path,
)

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class FakeJob:
    job_id: str
    name: str
    source_extraction: Path
    work_root: Path | None = None
    work_operations: Path | None = None
    effective_work_operations: Path | None = None
    profile_id: str = 'noark5'
    operation_ids: tuple[str, ...] = ()
    status: str = 'Klar'


class FakeSharedWorkbenchAPI:
    """Small faithful contract: all mutations use a shared jobs tuple."""
    def __init__(self):
        self.jobs = []
        self._active = None
        self._next = 1
        self.job_list_path = None
        self.dirty = False
        self.created = 0
        self.worker_starts = 0
        self.running = False
        self.settings = {}
        self.fail_workflow = False

    def workspace(self):
        return SimpleNamespace(jobs=tuple(self.jobs), active_job_id=self._active,
                               job_list_path=self.job_list_path)

    def job_details(self, job_id):
        item = next(j for j in self.jobs if j.job_id == job_id)
        operations = [SimpleNamespace(operation_id=x) for x in item.operation_ids]
        return SimpleNamespace(job=item, operations=operations)

    def create_job(self, *, source_extraction, name, profile_id):
        job_id = f'JOB-{self._next:03d}'
        self._next += 1
        self.created += 1
        obj = FakeJob(job_id, name, Path(source_extraction), profile_id=profile_id)
        self.jobs.append(obj)
        self._active = obj.job_id
        self.dirty = True
        return obj

    def update_storage(self, job_id, storage):
        obj = self.job_details(job_id).job
        obj.work_operations = Path(storage['work_operations'])
        obj.work_root = Path(storage['work_root'])
        obj.effective_work_operations = obj.work_operations
        self.dirty = True

    def set_workflow(self, job_id, operation_ids):
        if self.fail_workflow:
            raise ValueError('Simulert feil i opprettelse')
        self.job_details(job_id).job.operation_ids = tuple(operation_ids)
        self.dirty = True

    def use_selected_work_directly(self, job_id):
        self.job_details(job_id)

    def select_job(self, job_id):
        self.job_details(job_id)
        self._active = job_id

    def remove_job(self, job_id):
        self.jobs = [j for j in self.jobs if j.job_id != job_id]
        self.dirty = True

    def save_job_list(self, path=None):
        if path:
            self.job_list_path = Path(path)
        if not self.job_list_path:
            raise ValueError('Velg filnavn')
        data = {'file_type': 'noark5-workflow-manager-job-list',
                'format_version': 5, 'active_job_id': self._active,
                'jobs': [{'job_id': j.job_id, 'name': j.name,
                          'source_extraction': str(j.source_extraction),
                          'work_operations': str(j.work_operations),
                          'operations': list(j.operation_ids)} for j in self.jobs]}
        self.job_list_path.write_text(json.dumps(data), encoding='utf-8')
        self.dirty = False
        return self.job_list_path

    def open_job_list(self, path):
        self.job_list_path = Path(path)
        data = json.loads(self.job_list_path.read_text(encoding='utf-8'))
        self.jobs = []
        for entry in data['jobs']:
            work = Path(entry['work_operations'])
            self.jobs.append(FakeJob(entry['job_id'], entry['name'],
                                     Path(entry['source_extraction']), work,
                                     work, work, operation_ids=tuple(entry['operations'])))
        self._active = data['active_job_id']
        self._next = max([int(j.job_id.rsplit('-', 1)[-1]) for j in self.jobs] + [0]) + 1
        self.dirty = False


def plan(root, index, operations=('metadata_inventory', 'validate_xml_schema')):
    source = root / f'extract_{index}'
    work = root / f'work_{index}'
    return SimpleNamespace(source_extraction=source, work_root=work,
                           work_operations=work, operation_ids=operations)


def clean(_work, _source):
    return SimpleNamespace(kind='empty', count=0)


class ThreeJobsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.api = FakeSharedWorkbenchAPI()

    def test_three_basic_jobs_are_persisted_and_reopened_by_advanced(self):
        original = []
        for n in (1, 2, 3):
            outcome = register_basic_plan(self.api, plan(self.root, n),
                                          create_new=True, inspect=clean)
            original.append(outcome.job_id)
            self.assertTrue(outcome.created)
            self.assertEqual(len(self.api.workspace().jobs), n)
            self.assertEqual(self.api.worker_starts, 0)
        self.assertEqual(original, ['JOB-001', 'JOB-002', 'JOB-003'])
        self.assertEqual([x[0] for x in list_job_labels(self.api)], original)
        path = self.root / '1547_003_005_007.n5jobs'
        self.api.save_job_list(path)
        raw = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual([j['job_id'] for j in raw['jobs']], original)
        self.assertEqual(raw['active_job_id'], 'JOB-003')
        reopened = FakeSharedWorkbenchAPI()
        reopened.open_job_list(path)
        self.assertEqual([j.job_id for j in reopened.workspace().jobs], original)
        for n, job in enumerate(reopened.workspace().jobs, 1):
            self.assertEqual(job.source_extraction, plan(self.root, n).source_extraction)
            self.assertEqual(job.work_operations, plan(self.root, n).work_operations)
            self.assertEqual(job.operation_ids, plan(self.root, n).operation_ids)
        self.assertEqual(reopened.worker_starts, 0)
        # Selection in one mode is the selection in the other: one API.
        reopened.select_job('JOB-001')
        self.assertEqual(reopened.workspace().active_job_id, 'JOB-001')
        reopened.select_job('JOB-002')
        self.assertEqual(reopened.workspace().active_job_id, 'JOB-002')

    def test_duplicate_draft_reuses_job_not_creating_job_004(self):
        first = register_basic_plan(self.api, plan(self.root, 1),
                                    create_new=True, inspect=clean)
        second = register_basic_plan(self.api, plan(self.root, 1),
                                     create_new=True, inspect=clean)
        self.assertEqual(first.job_id, second.job_id)
        self.assertFalse(second.created)
        self.assertEqual(self.api.created, 1)

    def test_edit_existing_workflow_only_for_same_selected_job(self):
        first = register_basic_plan(self.api, plan(self.root, 1),
                                    create_new=True, inspect=clean)
        next_plan = plan(self.root, 1, ('metadata_inventory', 'run_noark5_xpath_tests_2026'))
        edited = register_basic_plan(self.api, next_plan, selected_job_id=first.job_id,
                                     create_new=False, inspect=clean)
        self.assertTrue(edited.workflow_changed)
        self.assertFalse(edited.created)
        self.assertEqual(self.api.job_details(first.job_id).job.operation_ids,
                         next_plan.operation_ids)
        with self.assertRaisesRegex(ValueError, 'andre kontroller'):
            register_basic_plan(self.api, plan(self.root, 1),
                                create_new=True, inspect=clean)

    def test_different_source_cannot_share_work_even_before_execution(self):
        first = register_basic_plan(self.api, plan(self.root, 1),
                                    create_new=True, inspect=clean)
        duplicate = plan(self.root, 2)
        duplicate.work_operations = plan(self.root, 1).work_operations
        duplicate.work_root = duplicate.work_operations
        with self.assertRaisesRegex(ValueError, 'allerede knyttet'):
            register_basic_plan(self.api, duplicate, create_new=True, inspect=clean)
        self.assertEqual([j.job_id for j in self.api.workspace().jobs], [first.job_id])

    def test_existing_job_cannot_silently_change_source_or_work(self):
        first = register_basic_plan(self.api, plan(self.root, 1),
                                    create_new=True, inspect=clean)
        with self.assertRaisesRegex(ValueError, 'Legg til uttrekk'):
            register_basic_plan(self.api, plan(self.root, 2),
                                selected_job_id=first.job_id, create_new=False, inspect=clean)
        self.assertEqual(self.api.job_details(first.job_id).job.source_extraction,
                         plan(self.root, 1).source_extraction)

    def test_external_work_needs_explicit_approval_not_just_path(self):
        nonempty = lambda _work, _source: SimpleNamespace(kind='unrelated', count=4)
        with self.assertRaisesRegex(ValueError, 'Bekreft Work'):
            register_basic_plan(self.api, plan(self.root, 1),
                                create_new=True, inspect=nonempty)
        self.assertFalse(self.api.workspace().jobs)
        result = register_basic_plan(self.api, plan(self.root, 1),
                                     create_new=True, inspect=nonempty, work_approved=True)
        self.assertTrue(result.created)

    def test_unknown_work_identity_is_never_overridden_by_approval(self):
        for kind in ('unknown_job', 'different_source', 'same_job'):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(ValueError, 'identitet'):
                    register_basic_plan(self.api, plan(self.root, 1),
                                        create_new=True, inspect=lambda *_: SimpleNamespace(kind=kind,count=1),
                                        work_approved=True)
        self.assertEqual(self.api.created, 0)

    def test_work_folder_with_joblist_needs_operator_confirmation(self):
        only_list = lambda *_: SimpleNamespace(kind='empty', count=1)
        with self.assertRaisesRegex(ValueError, 'Bekreft Work'):
            register_basic_plan(self.api, plan(self.root, 1),
                                create_new=True, inspect=only_list)
        self.assertTrue(register_basic_plan(self.api, plan(self.root, 1),
                                            create_new=True, inspect=only_list,
                                            work_approved=True).created)

    def test_rollback_removes_only_new_job_after_api_failure(self):
        register_basic_plan(self.api, plan(self.root, 1),
                            create_new=True, inspect=clean)
        self.api.fail_workflow = True
        with self.assertRaisesRegex(ValueError, 'Simulert'):
            register_basic_plan(self.api, plan(self.root, 2),
                                create_new=True, inspect=clean)
        self.assertEqual(len(self.api.jobs), 1)
        self.assertEqual(self.api.jobs[0].job_id, 'JOB-001')

    def test_no_disk_or_worker_side_effect_without_explicit_save(self):
        register_basic_plan(self.api, plan(self.root, 1),
                            create_new=True, inspect=clean)
        self.assertEqual(self.api.worker_starts, 0)
        self.assertFalse(list(self.root.iterdir()))
        self.assertTrue(self.api.dirty)

    def test_paths_compare_canonical_locations(self):
        self.assertTrue(same_path(self.root/'foo'/'..'/'one', self.root/'one'))
        self.assertFalse(same_path(None, self.root/'one'))


class GuiContractTests(unittest.TestCase):
    def test_gui_persistence_does_not_depend_on_nonexistent_api_dirty(self):
        source = (ROOT/'gui_qt/basic_multijob_v022_a1_2.py').read_text(encoding='utf-8')
        self.assertNotIn('self.api.dirty', source)
        self.assertIn('output = self.api.save_job_list()', source)
        self.assertIn('self._v022_save_failed', source)

    def test_main_entrypoint_uses_multi_job_extension(self):
        source = (ROOT/'gui_qt/__main__.py').read_text(encoding='utf-8')
        self.assertIn('from gui_qt.basic_multijob_v022_a1_2 import DwmMainWindow', source)
        self.assertIn('install_depot_profile_controls(window)', source)

    def test_new_control_is_distinct_from_adding_extraction(self):
        source = (ROOT/'gui_qt/basic_multijob_v022_a1_2.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        methods = {node.name: ast.get_source_segment(source, node)
                   for cls in ast.walk(tree) if isinstance(cls, ast.ClassDef)
                   for node in cls.body if isinstance(node, ast.FunctionDef)}
        self.assertIn('self.api.new_job_list()', methods['_a3_new_control'])
        self.assertNotIn('self.api.new_job_list(', methods['_v022_new_draft'])
        self.assertIn('self._reset_basic_selection()', methods['_a3_new_control'])
        self.assertIn('self._v022_register_current()', methods['_v022_new_draft'])

    def test_explicit_actions_and_automatic_work_selection(self):
        source = (ROOT/'gui_qt/basic_multijob_v022_a1_2.py').read_text(encoding='utf-8')
        for token in ('Legg til uttrekk', 'Lagre', 'Lagre som…',
                      'def _a3_accept_work(', 'def _leave_basic(',
                      'def _v022_choose_job(', 'def _start_basic_control('):
            self.assertIn(token, source)
        self.assertIn('self._v022_save_joblist_to_existing_file()', source)



class FakeQtIntegrationTests(unittest.TestCase):
    def test_basic_auto_registers_three_jobs_without_starting_and_can_select_any(self):
        """Import real a1.2 Qt subclass with lightweight Qt/Base stubs only."""
        import importlib.util
        import sys
        import types
        from unittest.mock import patch

        class Field:
            def __init__(self, value=''):
                self.value = value
            def text(self):
                return self.value
            def setText(self, value):
                self.value = str(value)
            def clear(self):
                self.value = ''

        class Message:
            class StandardButton:
                Yes = 1
                No = 2
            @staticmethod
            def information(*args):
                raise AssertionError('Unexpected QMessageBox.information: ' + repr(args))
            @staticmethod
            def warning(*args):
                raise AssertionError('Unexpected QMessageBox.warning: ' + repr(args))
            @staticmethod
            def question(*args):
                return Message.StandardButton.Yes

        class Base:
            def _enter_basic(self):
                self._basic_active = True
            def _leave_basic(self):
                self._basic_active = False
            def _a3_accept_work(self, folder):
                self.basic_work_path.setText(str(folder))
                self._a3_work_approval = (self.basic_source_path.text(), str(folder), 'empty')
            def _load_basic_active_job(self):
                if self._active_id:
                    job = self.api.job_details(self._active_id).job
                    self.basic_source_path.setText(job.source_extraction)
                    self.basic_work_path.setText(job.work_operations)
            def _reset_basic_selection(self):
                self.basic_source_path.clear()
                self.basic_work_path.clear()
                self._basic_job_id = None
            def _refresh(self, **_kw):
                pass
            def _a2_refresh_overview(self):
                pass
            def _sync_basic_status(self):
                pass
            def _a2_set_step(self, step):
                self.step = step
            def _remember_joblist(self, _path):
                pass
            def _selected_basic_controls(self):
                return ('dwm',)

        pkg = types.ModuleType('PySide6')
        qtwidgets = types.ModuleType('PySide6.QtWidgets')
        for name in ('QComboBox', 'QGroupBox', 'QHBoxLayout', 'QLabel', 'QPushButton', 'QVBoxLayout'):
            setattr(qtwidgets, name, type(name, (), {}))
        qtwidgets.QMessageBox = Message
        qtcore = types.ModuleType('PySide6.QtCore')
        qtcore.Qt = object()
        original_base = types.ModuleType('gui_qt.main_v020_a6')
        original_base.DwmMainWindow = Base
        basic_plan = types.ModuleType('app.basic_start_v0111_a1')
        basic_plan.prepare_basic_plan = lambda source, work, settings, controls: SimpleNamespace(
            source_extraction=Path(source), work_root=Path(work),
            work_operations=Path(work), operation_ids=('metadata_inventory',))
        basic_plan.existing_basic_job = lambda api, p: next(
            (j.job_id for j in api.jobs if same_path(j.source_extraction, p.source_extraction)
             and same_path(j.work_operations, p.work_operations)), None)
        work_guard = types.ModuleType('app.basic_work_guard_v0113_a3')
        current = {'api': None}
        def inspect_work_stub(work, _source):
            api = current['api']
            seen = bool(api and any(j.work_operations and same_path(j.work_operations, work)
                                    for j in api.jobs))
            # DWM metadata can make Work look like unknown_job after registration.
            return SimpleNamespace(kind='unknown_job' if seen else 'empty',
                                   count=1 if seen else 0)
        work_guard.inspect_work = inspect_work_stub
        imports = {'PySide6': pkg, 'PySide6.QtCore': qtcore,
                   'PySide6.QtWidgets': qtwidgets,
                   'gui_qt.main_v020_a6': original_base,
                   'app.basic_start_v0111_a1': basic_plan,
                   'app.basic_work_guard_v0113_a3': work_guard}
        with patch.dict(sys.modules, imports):
            spec = importlib.util.spec_from_file_location('test_multijob_gui_stub',
                ROOT/'gui_qt/basic_multijob_v022_a1_2.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            window = module.DwmMainWindow.__new__(module.DwmMainWindow)
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                api = FakeSharedWorkbenchAPI()
                api.settings = {}
                current['api'] = api
                api.job_list_path = root/'three_jobs.n5jobs'
                del api.dirty  # Real DWM API does not expose a dirty flag
                window.api = api
                window.basic_source_path = Field()
                window.basic_work_path = Field()
                window.basic_dias_label = Field()
                window.basic_dias_note = Field()
                window._worker = None
                window._active_id = None
                window._basic_job_id = None
                window._basic_active = True
                window._a2_pending_dirty = False
                window._v022_loading_job = False
                window._v022_draft = True
                window._a3_work_approval = None
                window._v022_refresh_selector = lambda **kw: None
                # Complete Basic Source/Work selections auto-save jobs without
                # any Start control or worker invocation.
                for index in (1, 2, 3):
                    if index > 1:
                        window._v022_new_draft()
                    window.basic_source_path.setText(root/f'extract_{index}')
                    window._a3_accept_work(root/f'work_{index}')
                    self.assertEqual(len(api.jobs), index)
                    self.assertTrue(api.job_list_path.exists())
                    self.assertEqual(window._a3_work_approval[2], 'same_job')
                self.assertEqual([j.job_id for j in api.jobs],
                                 ['JOB-001', 'JOB-002', 'JOB-003'])
                self.assertEqual(len(json.loads(api.job_list_path.read_text())['jobs']), 3)
                self.assertEqual(api.worker_starts, 0)
                window.v022_job_selector = SimpleNamespace(currentData=lambda: 'JOB-001')
                window._v022_choose_job(0)
                self.assertEqual(api.workspace().active_job_id, 'JOB-001')
                self.assertEqual(window.basic_source_path.text(), str(root/'extract_1'))
                self.assertEqual(window.basic_work_path.text(), str(root/'work_1'))
                self.assertEqual(len(api.jobs), 3)
                window._leave_basic()
                self.assertFalse(window._basic_active)
                window._enter_basic()
                self.assertTrue(window._basic_active)
                self.assertEqual(api.workspace().active_job_id, 'JOB-001')
                self.assertEqual(len(api.jobs), 3)
                reopened = FakeSharedWorkbenchAPI()
                reopened.open_job_list(api.job_list_path)
                self.assertEqual(len(reopened.workspace().jobs), 3)
                self.assertEqual(reopened.workspace().active_job_id, 'JOB-001')


if __name__ == '__main__':
    unittest.main()
