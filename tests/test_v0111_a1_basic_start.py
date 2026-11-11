"""Basic Source/Work planning, safe job reuse and no implicit filesystem writes."""
from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import sys
import tempfile
import tomllib
import unittest

from app.basic_start_v0111_a1 import (
    BASIC_WORKFLOW_ID, BasicControlPlan, ensure_separate_source_and_work,
    existing_basic_job, prepare_basic_plan, select_or_create_basic_job,
)
from version import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ('metadata_inventory', 'validate_xml_schema', 'analyse_arkivstruktur',
            'run_noark5_xpath_tests_2026', 'compose_noark5_views',
            'build_noark5_depot_report')


class MemoryApi:
    def __init__(self, jobs=(), operations=WORKFLOW):
        self.jobs = list(jobs)
        self.operations = operations
        self.calls = []
        self.next_id = 'JOB-NEW'
    def workspace(self):
        return SimpleNamespace(jobs=self.jobs)
    def job_details(self, job_id):
        return SimpleNamespace(operations=[SimpleNamespace(operation_id=i) for i in self.operations])
    def select_job(self, job_id):
        self.calls.append(('select', job_id))
    def create_job(self, **kwargs):
        self.calls.append(('create', kwargs))
        self.jobs.append(SimpleNamespace(job_id=self.next_id,
                         source_extraction=kwargs['source_extraction'], work_operations=None))
        return SimpleNamespace(job_id=self.next_id)
    def update_storage(self, job_id, paths):
        self.calls.append(('storage', job_id, paths))
        self.jobs[-1].work_operations = paths['work_operations']
    def set_workflow(self, job_id, operation_ids):
        self.calls.append(('workflow', job_id, tuple(operation_ids)))
    def use_selected_work_directly(self, job_id):
        self.calls.append(('direct', job_id))
    def remove_job(self, job_id):
        self.calls.append(('remove', job_id))
        self.jobs = [job for job in self.jobs if job.job_id != job_id]


class PathSafetyTests(unittest.TestCase):
    def test_work_inside_original_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'uttrekk'
            source.mkdir()
            with self.assertRaisesRegex(ValueError, 'utenfor'):
                ensure_separate_source_and_work(source, source / 'work')
            with self.assertRaisesRegex(ValueError, 'utenfor'):
                ensure_separate_source_and_work(source / 'sub', source)
            ensure_separate_source_and_work(source, Path(tmp) / 'work')

    def test_symlink_work_inside_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'
            source.mkdir()
            child = source / 'hidden-work'
            child.mkdir()
            alias = Path(tmp) / 'alias'
            try:
                alias.symlink_to(child, target_is_directory=True)
            except OSError:
                self.skipTest('Symlink creation is unavailable on this machine')
            with self.assertRaises(ValueError):
                ensure_separate_source_and_work(source, alias)

    def test_plan_uses_selected_work_directly_and_existing_dwm_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (source / 'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf-8')
            work = root / 'workroot'
            work.mkdir()
            calls = []
            def validate(path, *, profile_id):
                calls.append(('validate', path, profile_id))
                return () if (path / 'arkivstruktur.xml').is_file() else (
                    SimpleNamespace(message='Uttrekk mangler'),)
            def workflow(_id):
                calls.append(('sequence', _id))
                return SimpleNamespace(profile_id='noark5', operation_ids=WORKFLOW)
            stubs = {
                'app.job_preflight_v018_a6': SimpleNamespace(
                    check_extraction_folder=validate),
                'app.storage_profiles_v0110_a2': SimpleNamespace(
                    resolve_storage_profile=lambda _settings: 'standard_enkel'),
                'app.workflow_sequences': SimpleNamespace(workflow_sequence_by_id=workflow),
            }
            with patch.dict(sys.modules, stubs):
                result = prepare_basic_plan(source, work, {'app_work_subfolder': 'dwm'})
            self.assertEqual(result.source_extraction, source)
            self.assertEqual(result.work_root, work)
            self.assertEqual(result.work_operations, work)
            self.assertEqual(result.operation_ids, WORKFLOW)
            self.assertIn(('validate', source, 'noark5'), calls)
            self.assertIn(('sequence', BASIC_WORKFLOW_ID), calls)
            self.assertEqual(list(work.iterdir()), [], 'Planning must not make folders')

    def test_plan_refuses_work_that_is_inside_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'uttrekk'
            source.mkdir()
            (source / 'arkivstruktur.xml').write_text('dummy', encoding='utf-8')
            work = source / 'work'
            work.mkdir()
            modules = {
                'app.job_preflight_v018_a6': SimpleNamespace(
                    check_extraction_folder=lambda *_args, **_kwargs: ()),
                'app.storage_profiles_v0110_a2': SimpleNamespace(
                    resolve_storage_profile=lambda _settings: 'standard_enkel'),
                'app.workflow_sequences': SimpleNamespace(
                    workflow_sequence_by_id=lambda _id: SimpleNamespace(
                        profile_id='noark5', operation_ids=WORKFLOW)),
            }
            with patch.dict(sys.modules, modules):
                with self.assertRaisesRegex(ValueError, 'utenfor'):
                    prepare_basic_plan(source, work)

    def test_plan_refuses_missing_work_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            modules = {
                'app.job_preflight_v018_a6': SimpleNamespace(
                    check_extraction_folder=lambda *_a, **_k: (),
                    propose_work_location=lambda *_a, **_k: None),
                'app.storage_profiles_v0110_a1': SimpleNamespace(
                    propose_profile_work_location=lambda *_a, **_k: None),
                'app.storage_profiles_v0110_a2': SimpleNamespace(
                    resolve_storage_profile=lambda _settings: 'standard_enkel'),
                'app.workflow_sequences': SimpleNamespace(workflow_sequence_by_id=lambda _id: None),
            }
            with patch.dict(sys.modules, modules):
                with self.assertRaisesRegex(ValueError, 'Work-mappen finnes ikke'):
                    prepare_basic_plan(root, root / 'absent')

    def test_no_implicit_arkade_or_aip(self):
        self.assertEqual(BASIC_WORKFLOW_ID, 'noark5_dwm')
        self.assertNotIn('dias_package', WORKFLOW)
        self.assertNotIn('arkade5_noark5_test', WORKFLOW)


class ApiUseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        work = base / 'work'
        work.mkdir()
        self.plan = BasicControlPlan(base / 'source', work, work,
                                     'standard_enkel', WORKFLOW)

    def test_new_job_uses_existing_api_without_running_or_mkdir(self):
        api = MemoryApi()
        job_id, created = select_or_create_basic_job(api, self.plan)
        self.assertTrue(created)
        self.assertEqual(job_id, 'JOB-NEW')
        self.assertEqual([item[0] for item in api.calls], ['create', 'storage', 'workflow', 'direct'])
        self.assertEqual(api.calls[1][2]['work_root'], str(self.plan.work_root))
        self.assertEqual(list(self.plan.work_operations.iterdir()), [])

    def test_matching_job_is_reused_and_not_duplicated(self):
        original = SimpleNamespace(job_id='JOB-OLD',
                    source_extraction=str(self.plan.source_extraction),
                    work_operations=str(self.plan.work_operations))
        api = MemoryApi([original])
        job_id, created = select_or_create_basic_job(api, self.plan)
        self.assertFalse(created)
        self.assertEqual(job_id, 'JOB-OLD')
        self.assertEqual(api.calls, [('select', 'JOB-OLD')])

    def test_different_workflow_is_never_run_as_basic(self):
        original = SimpleNamespace(job_id='JOB-OLD',
                    source_extraction=str(self.plan.source_extraction),
                    work_operations=str(self.plan.work_operations))
        api = MemoryApi([original], operations=('dias_package',))
        with self.assertRaisesRegex(ValueError, 'annen arbeidsflyt'):
            existing_basic_job(api, self.plan)
        self.assertEqual(api.calls, [])

    def test_nonempty_work_folder_is_not_used_for_new_job(self):
        (self.plan.work_operations / 'someones-file.txt').write_text('not DWM')
        api = MemoryApi()
        with self.assertRaisesRegex(ValueError, 'ikke tom'):
            select_or_create_basic_job(api, self.plan)
        self.assertFalse(api.calls)

    def test_legacy_job_in_same_work_root_requires_advanced_mode(self):
        original = SimpleNamespace(
            job_id='JOB-OLD', source_extraction=str(self.plan.source_extraction),
            work_root=str(self.plan.work_root),
            work_operations=str(self.plan.work_root / 'work'),
            effective_work_operations=str(self.plan.work_root / 'work' / 'dwm' / 'job-001'),
        )
        api = MemoryApi([original])
        with self.assertRaisesRegex(ValueError, 'eldre mappeoppsett'):
            select_or_create_basic_job(api, self.plan)
        self.assertFalse(api.calls)

    def test_failed_configuration_discards_new_draft(self):
        class FailApi(MemoryApi):
            def update_storage(self, job_id, paths):
                raise ValueError('Invalid storage')
        api = FailApi()
        with self.assertRaisesRegex(ValueError, 'Invalid storage'):
            select_or_create_basic_job(api, self.plan)
        self.assertEqual(api.calls[-1], ('remove', 'JOB-NEW'))
        self.assertEqual(api.jobs, [])


class VersionTests(unittest.TestCase):
    def test_alpha_and_distribution(self):
        self.assertEqual(APP_NAME, 'Data Workflow Manager')
        import re
        match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-a(\d+))?', VERSION)
        self.assertIsNotNone(match, VERSION)
        release = tuple(map(int, match.groups()[:3]))
        self.assertGreaterEqual(release, (0, 1, 11))
        if release == (0, 1, 11) and match.group(4) is not None:
            self.assertGreaterEqual(int(match.group(4)), 1)
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            self.assertEqual(tomllib.load(stream)['project']['version'], VERSION.replace('-a', 'a'))
        # tests/run_tests.py adds historical alpha markers to Path.read_text().
        # Read the physical release/alpha file instead of that test-only view.
        with (ROOT / 'version.py').open('r', encoding='utf-8') as handle:
            source = handle.read()
        self.assertEqual(source,
                         f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n')


if __name__ == '__main__':
    unittest.main()
