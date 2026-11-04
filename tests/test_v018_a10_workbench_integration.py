"""a10: real WorkPersistenceMixin methods, with only outer Qt/registry mocked."""
from __future__ import annotations

import ast
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from noark5_workflow.core.job import Job, JobBatch, JobStatus
from noark5_workflow.core.job_store import load_job_list, save_job_list
from noark5_workflow.core.work_job_store import WorkJobStore, WorkJobStoreError

ROOT = Path(__file__).resolve().parents[1]


class DwmApiError(RuntimeError):
    pass


def effective_work_operations(base, app, rule, job, position):
    if base is None:
        return None
    result = Path(base)
    if app:
        result /= app
    if rule:
        result /= rule  # test case deliberately avoids rule substitution
    return result


def load_mixin():
    source = (ROOT / 'app' / 'work_persistence_v018_a10.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    body = [n for n in tree.body if
            (isinstance(n, ast.ClassDef) and n.name == 'WorkPersistenceMixin')
            or (isinstance(n, ast.FunctionDef) and n.name == '_path_overlap')]
    module = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
    ns = {
        'Path': Path, 'UUID': UUID, 'uuid4': uuid4, 'Job': Job,
        'DwmApiError': DwmApiError, 'WorkJobStore': WorkJobStore,
        'WorkJobStoreError': WorkJobStoreError, 'save_job_list': save_job_list,
        'effective_work_operations': effective_work_operations, 'VERSION': '0.1.8-a10',
    }
    exec(compile(module, '<work_persistence_v018_a10>', 'exec'), ns)
    return ns['WorkPersistenceMixin']


class Base:
    def _emit(self, kind, job=None, *, message='', progress=None):
        self.events.append(kind)


class Facade(load_mixin(), Base):
    def __init__(self, root):
        self.root = root
        self.work = root / 'work' / 'repository_operations' / 'dwm'
        self.work.mkdir(parents=True)
        self.source = root / 'source'
        self.source.mkdir()
        self.job_list = root / 'joblists' / 'collection.n5jobs'
        self.settings = {'app_work_subfolder': 'dwm'}
        self._work_references = {}
        self._unavailable_work_ids = frozenset()
        self._batch = JobBatch(); self._batch.output_subfolder_rule = ''
        self._active_job_id = 'JOB-001'
        self._path = self.job_list
        self._guard = threading.Lock()
        self._dirty = False
        self._running = False
        self.events = []
        self.job = Job('JOB-001', name='Archive', profile_id='noark5',
                       source_root=self.source, source_extraction=self.source,
                       work_operations=self.work.parent, workflow_ids=['one','two'])
        self._batch.add(self.job)

    def _require_job(self, job_id):
        job = self._batch.get(job_id)
        if job is None:
            raise DwmApiError('Job not found')
        return job

    def _assert_idle(self):
        if self._running:
            raise DwmApiError('Busy')

    def _view(self, job, position):
        root = (self._work_references[job.job_id].parent
                if job.job_id in self._work_references
                else effective_work_operations(job.work_operations, 'dwm', '', job, position))
        return SimpleNamespace(job_id=job.job_id, name=job.name,
                               effective_work_operations=str(root) if root else None)


class WorkbenchIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.api = Facade(Path(temp.name))

    def test_registration_requires_approved_existing_folder(self):
        self.api.work.rmdir()
        with self.assertRaises(DwmApiError):
            self.api._register_work_job('JOB-001', reason='work.migrated')
        self.assertFalse((self.api.work / 'job.json').exists())

    def test_work_migration_before_index_and_recovery(self):
        ref = self.api.migrate_job_to_work('JOB-001')
        self.assertTrue(ref.is_file())
        self.assertTrue(self.api._dirty)
        self.api._write_job_list_file(self.api.job_list, 'JOB-001')
        loaded = load_job_list(self.api.job_list)
        self.assertEqual(loaded.batch.get('JOB-001').workflow_ids, ['one','two'])
        self.assertIn('JOB-001', loaded.work_references)
        self.assertEqual(json.loads(self.api.job_list.read_text())['format_version'], 5)

    def test_job_changes_write_work_before_user_saves_list(self):
        self.api.migrate_job_to_work('JOB-001')
        self.api.job.name = 'New name'
        self.api._emit('job.renamed', self.api.job)
        self.assertEqual(WorkJobStore(self.api.work).load().name, 'New name')
        self.assertFalse(self.api.job_list.exists())
        self.assertIn('job.renamed', self.api.events)

    def test_run_state_survives_a_broken_joblist_write(self):
        self.api.migrate_job_to_work('JOB-001')
        self.api.job.status = JobStatus.OK
        self.api.job.progress = 1.0
        self.api.job.next_operation_index = 2
        # Deliberately fail *index* write, after authoritative Work commit.
        self.api._path = self.api.root / 'blocked.n5jobs'
        self.api._path.mkdir()  # cannot replace a directory with the index file
        self.api._persist_updated_job(self.api.job, 'JOB-001')
        self.assertIn('Work-status', self.api._work_index_warning)
        self.assertIn('joblist.index_write_failed', self.api.events)
        work_job = WorkJobStore(self.api.work).load()
        self.assertEqual(work_job.status, JobStatus.OK)
        self.assertEqual(work_job.next_operation_index, 2)

    def test_recover_into_empty_list_without_original_n5jobs(self):
        self.api.migrate_job_to_work('JOB-001')
        fresh = Facade(self.api.root / 'fresh')
        fresh._batch = JobBatch()
        fresh._active_job_id = None
        view = fresh.recover_job_from_work(self.api.work)
        self.assertEqual(view.job_id, 'JOB-001')
        self.assertEqual(fresh._batch.get('JOB-001').job_uid, self.api.job.job_uid)
        self.assertFalse(fresh.job_list.exists())
        self.assertTrue((self.api.work / 'job.json').is_file())

    def test_recovery_into_list_with_same_job_number_relabels_not_duplicates(self):
        self.api.migrate_job_to_work('JOB-001')
        fresh = Facade(self.api.root / 'fresh')
        view = fresh.recover_job_from_work(self.api.work)
        self.assertEqual(view.job_id, 'JOB-002')
        self.assertEqual(fresh._batch.get('JOB-002').job_uid, self.api.job.job_uid)
        self.assertNotEqual(fresh._batch.get('JOB-001').job_id,
                            fresh._batch.get('JOB-002').job_id)
        with self.assertRaises(DwmApiError):
            fresh.recover_job_from_work(self.api.work)

    def test_subjob_event_does_not_advance_parent_state(self):
        self.api.migrate_job_to_work('JOB-001')
        self.api._emit('subjob.finished', self.api.job, message='one OK')
        restored = WorkJobStore(self.api.work).load()
        self.assertEqual(restored.status, JobStatus.READY)
        self.assertEqual(restored.next_operation_index, 0)
        self.assertEqual(restored.progress, 0)
        events = [json.loads(line) for line in (self.api.work/'job-events.jsonl').read_text().splitlines()]
        self.assertIn('subjob.finished', [e['kind'] for e in events])

    def test_source_work_overlap_is_rejected_without_writes(self):
        self.api.job.work_operations = self.api.source
        with self.assertRaises(DwmApiError):
            self.api._register_work_job('JOB-001', reason='work.migrated')
        self.assertFalse((self.api.source / 'job.json').exists())


class WiringTests(unittest.TestCase):
    def test_workbench_runner_and_gui_are_wired(self):
        app = (ROOT / 'app' / 'application_api.py').read_text(encoding='utf-8')
        workbench = (ROOT / 'app' / 'workbench_api_v018_a3.py').read_text(encoding='utf-8')
        gui = (ROOT / 'gui_qt' / 'main_window.py').read_text(encoding='utf-8')
        self.assertIn('self._persist_updated_job(updated, job_id)', app)
        self.assertIn('WorkPersistenceMixin, SelectiveSubjobMixin, DwmApplication', workbench)
        self.assertIn('self._register_work_job(job_id, reason="work.initialized_before_run")', workbench)
        self.assertIn('self._register_work_job(job_id, reason="work.provisioned")', workbench)
        self.assertIn('self.api.recover_job_from_work(selected)', gui)
        self.assertIn('self.api.migrate_job_to_work(self._active_id)', gui)
        self.assertIn('Åpne jobb fra DWM-arbeidsområde', gui)
        self.assertIn('Lagre valgt jobb i Work', gui)


if __name__ == '__main__':
    unittest.main()
