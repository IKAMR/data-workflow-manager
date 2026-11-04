"""a10: Work is authoritative; job lists are disposable, mixed-format indexes."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from noark5_workflow.core.job import Job, JobBatch, JobStatus
from noark5_workflow.core.job_store import (
    FILE_TYPE, JobListFormatError, load_job_list, save_job_list,
)
from noark5_workflow.core.work_job_store import WorkJobStore, WorkJobStoreError


class WorkFirstStorageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.joblists = self.root / 'joblists'
        self.work = self.root / 'separate-work' / 'repository_operations' / 'dwm'
        self.work.mkdir(parents=True)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'unchanged.txt').write_text('original', encoding='utf-8')
        self.listpath = self.joblists / 'project.n5jobs'

    def job(self, *, id='JOB-001', profile='noark5', folder=None):
        directory = folder or self.work
        job = Job(
            job_id=id, name='Extract', profile_id=profile,
            source_root=self.source, source_extraction=self.source,
            work_operations=directory.parent,
            workflow_ids=['metadata_inventory', 'validate_xml_schema'],
            operation_params={'metadata_inventory': {'some_flag': 'tested'}},
            checkpoint_after=['metadata_inventory'],
        )
        job.job_uid = str(uuid4())
        job.production_system_ref = 'production-system-A'
        return job

    def test_write_and_recover_complete_definition_without_joblist(self):
        job = self.job()
        ref = WorkJobStore(self.work).write(job, event_kind='work.initialized')
        self.assertEqual(ref, self.work / 'job.json')
        self.assertTrue((self.work / 'job-state.json').is_file())
        self.assertTrue((self.work / 'job-events.jsonl').is_file())
        restored = WorkJobStore(self.work).load()
        self.assertEqual(restored.job_uid, job.job_uid)
        self.assertEqual(restored.profile_id, 'noark5')
        self.assertEqual(restored.source_extraction, self.source)
        self.assertEqual(restored.work_operations, self.work.parent)
        self.assertEqual(restored.workflow_ids, job.workflow_ids)
        self.assertEqual(restored.operation_params, job.operation_params)
        self.assertEqual(restored.checkpoint_after, job.checkpoint_after)
        self.assertEqual(restored.production_system_ref, 'production-system-A')
        self.assertEqual((self.source / 'unchanged.txt').read_text(encoding='utf-8'), 'original')

    def test_index_contains_reference_and_status_not_full_definition(self):
        job = self.job()
        ref = WorkJobStore(self.work).write(job, event_kind='work.initialized')
        batch = JobBatch(); batch.add(job)
        save_job_list(self.listpath, batch, active_job_id=job.job_id,
                      work_references={job.job_id: ref})
        data = json.loads(self.listpath.read_text(encoding='utf-8'))
        self.assertEqual(data['format_version'], 5)
        entry = data['jobs'][0]
        self.assertEqual(entry['entry_type'], 'work_ref')
        self.assertNotIn('workflow_ids', entry)
        self.assertNotIn('source_extraction', entry)
        self.assertNotIn('operation_params', entry)
        self.assertEqual(load_job_list(self.listpath).batch.get(job.job_id).workflow_ids,
                         job.workflow_ids)

    def test_work_status_overrides_stale_joblist_status(self):
        job = self.job()
        ref = WorkJobStore(self.work).write(job, event_kind='created')
        batch = JobBatch(); batch.add(job)
        save_job_list(self.listpath, batch, work_references={job.job_id: ref})
        job.status = JobStatus.OK
        job.next_operation_index = 2
        job.progress = 1.0
        job.message = 'Workflow fullført'
        WorkJobStore(self.work).write(job, event_kind='run.finished')
        index = json.loads(self.listpath.read_text(encoding='utf-8'))
        self.assertEqual(index['jobs'][0]['status'], JobStatus.READY.value)
        restored = load_job_list(self.listpath).batch.get(job.job_id)
        self.assertEqual(restored.status, JobStatus.OK)
        self.assertEqual(restored.progress, 1.0)
        self.assertEqual(restored.next_operation_index, 2)

    def test_joblist_does_not_need_to_exist_to_recover_status(self):
        job = self.job()
        job.status = JobStatus.FAILED
        job.message = 'Check failed'
        WorkJobStore(self.work).write(job, event_kind='run.error')
        self.assertFalse(self.listpath.exists())
        recovered = WorkJobStore(self.work).load()
        self.assertEqual((recovered.status, recovered.message),
                         (JobStatus.FAILED, 'Check failed'))

    def test_conflicting_job_ownership_cannot_overwrite_existing_work(self):
        first = self.job()
        second = self.job()
        store = WorkJobStore(self.work)
        store.write(first, event_kind='created')
        original = store.definition_path.read_bytes()
        with self.assertRaises(WorkJobStoreError):
            store.write(second, event_kind='created')
        self.assertEqual(store.definition_path.read_bytes(), original)
        self.assertEqual(store.load().job_uid, first.job_uid)

    def test_index_refuses_uid_substitution(self):
        job = self.job()
        ref = WorkJobStore(self.work).write(job, event_kind='created')
        batch = JobBatch(); batch.add(job)
        save_job_list(self.listpath, batch, work_references={job.job_id: ref})
        data = json.loads(self.listpath.read_text(encoding='utf-8'))
        data['jobs'][0]['job_uid'] = str(uuid4())
        self.listpath.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(JobListFormatError):
            load_job_list(self.listpath)

    def test_disconnected_work_returns_explicit_last_known_index(self):
        job = self.job()
        ref = WorkJobStore(self.work).write(job, event_kind='created')
        batch = JobBatch(); batch.add(job)
        save_job_list(self.listpath, batch, work_references={job.job_id: ref})
        moved = self.work.with_name('temporarily-disconnected')
        self.work.rename(moved)
        loaded = load_job_list(self.listpath)
        self.assertIn('JOB-001', loaded.unavailable_work_job_ids)
        self.assertIsNone(loaded.batch.get('JOB-001').source_extraction)
        self.assertIn('JOB-001', loaded.work_references)
        moved.rename(self.work)
        restored = load_job_list(self.listpath)
        self.assertFalse(restored.unavailable_work_job_ids)
        self.assertEqual(restored.batch.get('JOB-001').source_extraction, self.source)

    def test_draft_does_not_create_work(self):
        draft = self.job(folder=self.root / 'not-provisioned' / 'dwm')
        batch = JobBatch(); batch.add(draft)
        save_job_list(self.listpath, batch, work_references={})
        self.assertFalse((self.root / 'not-provisioned').exists())
        data = json.loads(self.listpath.read_text(encoding='utf-8'))
        self.assertEqual(data['jobs'][0]['entry_type'], 'draft')
        self.assertEqual(load_job_list(self.listpath).batch.get('JOB-001').workflow_ids,
                         draft.workflow_ids)

    def test_legacy_v4_files_still_load(self):
        job = self.job()
        batch = JobBatch(); batch.add(job)
        save_job_list(self.listpath, batch)
        data = json.loads(self.listpath.read_text(encoding='utf-8'))
        self.assertEqual(data['format_version'], 4)
        self.assertEqual(load_job_list(self.listpath).batch.get('JOB-001').workflow_ids,
                         job.workflow_ids)

    def test_v4_original_is_backed_up_before_first_v5_save(self):
        job = self.job()
        batch = JobBatch(); batch.add(job)
        save_job_list(self.listpath, batch)
        original = self.listpath.read_bytes()
        ref = WorkJobStore(self.work).write(job, event_kind='created')
        save_job_list(self.listpath, batch, work_references={job.job_id: ref})
        backup = self.listpath.with_name(self.listpath.name + '.pre-a10.bak')
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(json.loads(self.listpath.read_text())['format_version'], 5)
        # Subsequent saves never rewrite the historical original.
        job.status = JobStatus.OK
        save_job_list(self.listpath, batch, work_references={job.job_id: ref})
        self.assertEqual(backup.read_bytes(), original)

    def test_v5_cannot_be_demoted_by_legacy_save(self):
        job = self.job()
        batch = JobBatch(); batch.add(job)
        ref = WorkJobStore(self.work).write(job, event_kind='created')
        save_job_list(self.listpath, batch, work_references={job.job_id: ref})
        index_bytes = self.listpath.read_bytes()
        with self.assertRaises(JobListFormatError):
            save_job_list(self.listpath, batch)
        self.assertEqual(self.listpath.read_bytes(), index_bytes)

    def test_mixed_siard_and_noark5_jobs_have_separate_identity_and_status(self):
        noark = self.job(profile='noark5')
        siard_root = self.root / 'work-siard' / 'dwm'; siard_root.mkdir(parents=True)
        siard = self.job(id='JOB-002', profile='siard', folder=siard_root)
        noark.status = JobStatus.OK
        noark.progress = 1.0
        noark.next_operation_index = 2
        refs = {
            'JOB-001': WorkJobStore(self.work).write(noark, event_kind='run.finished'),
            'JOB-002': WorkJobStore(siard_root).write(siard, event_kind='work.initialized'),
        }
        batch = JobBatch(); batch.add(noark); batch.add(siard)
        save_job_list(self.listpath, batch, work_references=refs)
        recovered = load_job_list(self.listpath).batch
        self.assertEqual(len(recovered.jobs()), 2)
        a, b = recovered.jobs()
        self.assertEqual((a.profile_id, b.profile_id), ('noark5', 'siard'))
        self.assertNotEqual(a.job_uid, b.job_uid)
        self.assertEqual(a.production_system_ref, b.production_system_ref)
        self.assertEqual(a.status, JobStatus.OK)
        self.assertEqual(b.status, JobStatus.READY)

    def test_event_fallback_when_state_file_corrupted(self):
        job = self.job()
        job.status = JobStatus.OK; job.progress = 1.0
        store = WorkJobStore(self.work)
        store.write(job, event_kind='run.finished')
        store.state_path.write_text('{broken json', encoding='utf-8')
        restored = store.load()
        self.assertEqual(restored.status, JobStatus.OK)
        self.assertEqual(restored.progress, 1.0)

    def test_event_entries_are_append_only_and_have_stable_uid(self):
        job = self.job()
        store = WorkJobStore(self.work)
        store.write(job, event_kind='created')
        job.status = JobStatus.OK
        store.write(job, event_kind='run.finished')
        events = [json.loads(line) for line in store.events_path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual([event['kind'] for event in events], ['created','run.finished'])
        self.assertEqual({event['job_uid'] for event in events}, {job.job_uid})

    def test_work_write_requires_preexisting_approved_directory(self):
        folder = self.root / 'not-yet-approved' / 'dwm'
        job = self.job(folder=folder)
        with self.assertRaises(WorkJobStoreError):
            WorkJobStore(folder).write(job, event_kind='created')
        self.assertFalse(folder.exists())

    def test_old_log_aliases_survive_joblist_renumbering(self):
        job = self.job()
        store = WorkJobStore(self.work)
        store.write(job, event_kind='created')
        job.job_id = 'JOB-002'
        store.write(job, event_kind='job.recovered')
        aliases = store.load()._work_job_aliases
        self.assertEqual(aliases, ('JOB-001', 'JOB-002'))
        definition = json.loads(store.definition_path.read_text(encoding='utf-8'))
        self.assertEqual(definition['job_list_aliases'], ['JOB-001','JOB-002'])

    def test_work_json_is_format_neutral(self):
        job = self.job(profile='siard')
        WorkJobStore(self.work).write(job, event_kind='created')
        doc = json.loads((self.work / 'job.json').read_text(encoding='utf-8'))
        self.assertEqual(doc['file_type'], 'dwm-work-job')
        self.assertEqual(doc['job']['profile_id'], 'siard')
        self.assertEqual(doc['relationships'], {'related_job_uids': []})

    def test_work_index_survives_job_id_alias_change(self):
        job = self.job()
        ref = WorkJobStore(self.work).write(job, event_kind='created')
        batch = JobBatch(); job.job_id = 'JOB-032'; batch.add(job)
        save_job_list(self.listpath, batch, work_references={'JOB-032': ref})
        recovered = load_job_list(self.listpath).batch.get('JOB-032')
        self.assertEqual(recovered.job_id, 'JOB-032')
        self.assertEqual(recovered.job_uid, job.job_uid)


if __name__ == '__main__':
    unittest.main()
