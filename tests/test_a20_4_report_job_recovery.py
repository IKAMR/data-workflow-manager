"""a20.4: read-only recovery from stored DWM report artifacts."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from noark5_workflow.reporting.report_job_recovery_a204 import (
    RecoveryCancelled, RecoveryError, discover_report_jobs, save_recovered_report_jobs,
)


def add_report(work, jobid, run, *, source='G:/noark5/1535_001_data_noark5', manifest=True,
               report=True, body=None):
    path = work / 'noark5_reports' / 'depot_validation' / (jobid+'__RUN-'+run)
    path.mkdir(parents=True)
    if report:
        (path / 'depot_validation_report.json').write_text(json.dumps(
            body if body is not None else {'summary':{'archive_part_count':2},'archive_parts':[]}), encoding='utf-8')
    if manifest:
        (path / 'artifact_manifest.json').write_text(json.dumps(
            {'schema_version':2,'job_id':jobid,'source_extraction':source,
             'work_operations_effective':str(work),
             'operation_id':'build_noark5_depot_report'}), encoding='utf-8')
    return path


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_one_root_multiple_jobs_without_original_jobfile(self):
        work = self.root / '1535' / 'repository_operations' / 'dwm'
        add_report(work,'JOB-001','01',source='G:/1535_001_Sak_noark5')
        add_report(work,'JOB-002','02',source='G:/1535_002_Bygg_noark5')
        plan=discover_report_jobs(work.parent.parent)
        self.assertEqual(len(plan.jobs),2)
        self.assertEqual([x.job_id for x in plan.jobs],['JOB-001','JOB-002'])
        self.assertEqual(plan.jobs[0].work_operations,work)
        self.assertEqual(plan.jobs[0].name,'1535_001_Sak_noark5')
        self.assertTrue(plan.jobs[0].manifest_verified)

    def test_multiple_verified_runs_same_job_one_entry(self):
        work=self.root/'dwm'
        add_report(work,'JOB-001','a')
        add_report(work,'JOB-001','b')
        plan=discover_report_jobs(work)
        self.assertEqual(len(plan.jobs),1)
        self.assertEqual(plan.jobs[0].original_runs,2)

    def test_distinct_roots_unique_ids_can_combine(self):
        parent=self.root/'collection'
        add_report(parent/'1535'/'repository_operations'/'dwm','JOB-001','a')
        add_report(parent/'1532'/'repository_operations'/'dwm','JOB-002','b')
        plan=discover_report_jobs(parent)
        self.assertEqual(len(plan.jobs),2)
        self.assertEqual(len(plan.report_roots),2)

    def test_duplicate_ids_in_different_work_roots_are_rejected(self):
        base=self.root/'collection'
        add_report(base/'1535'/'repository_operations'/'dwm','JOB-001','a')
        add_report(base/'1547'/'repository_operations'/'dwm','JOB-001','b')
        with self.assertRaisesRegex(RecoveryError,'flere arbeidsområder'):
            discover_report_jobs(base)

    def test_one_id_multiple_sources_are_rejected(self):
        work=self.root/'dwm'
        add_report(work,'JOB-001','a',source='G:/1535_001_a')
        add_report(work,'JOB-001','b',source='G:/1535_002_b')
        with self.assertRaisesRegex(RecoveryError,'flere ulike uttrekk'):
            discover_report_jobs(work)

    def test_unverified_legacy_single_run_is_allowed_but_warned(self):
        work=self.root/'dwm'
        add_report(work,'JOB-009','a',manifest=False)
        plan=discover_report_jobs(work)
        self.assertEqual(len(plan.jobs),1)
        self.assertFalse(plan.jobs[0].manifest_verified)
        self.assertIn('uten manifest',' '.join(plan.warnings))

    def test_unverified_multiple_runs_fail_closed(self):
        work=self.root/'dwm'
        add_report(work,'JOB-001','a',manifest=False)
        add_report(work,'JOB-001','b',manifest=False)
        with self.assertRaisesRegex(RecoveryError,'mangler verifisert'):
            discover_report_jobs(work)

    def test_manifest_mismatch_never_attributed_to_other_job(self):
        work=self.root/'dwm'
        run=add_report(work,'JOB-001','a')
        meta=run/'artifact_manifest.json'
        data=json.loads(meta.read_text(encoding='utf8'))
        data['job_id']='JOB-002'
        meta.write_text(json.dumps(data), encoding='utf8')
        with self.assertRaisesRegex(RecoveryError,'Ingen lesbare'):
            discover_report_jobs(work)

    def test_corrupt_report_skipped_without_false_success(self):
        work=self.root/'dwm'
        run=add_report(work,'JOB-001','a')
        (run/'depot_validation_report.json').write_text('not JSON',encoding='utf8')
        with self.assertRaisesRegex(RecoveryError,'Ingen lesbare'):
            discover_report_jobs(work)

    def test_source_payload_not_traversed(self):
        work=self.root/'dwm'
        add_report(work,'JOB-003','a')
        doc=self.root/'DOKUMENT'/'deep'/'dwm'
        add_report(doc,'JOB-999','a')
        plan=discover_report_jobs(self.root)
        self.assertEqual([x.job_id for x in plan.jobs],['JOB-003'])

    def test_no_normal_report_no_job(self):
        (self.root/'dwm'/'noark5_tests').mkdir(parents=True)
        with self.assertRaisesRegex(RecoveryError,'Ingen lagrede depotrapporter'):
            discover_report_jobs(self.root/'dwm')

    def test_stop_before_discovery(self):
        cancel=Event();cancel.set()
        with self.assertRaises(RecoveryCancelled):
            discover_report_jobs(self.root, cancelled=cancel)

    def test_save_native_list_has_no_original_extraction_source_and_no_workflow(self):
        work=self.root/'dwm'
        add_report(work,'JOB-001','a')
        plan=discover_report_jobs(work)
        native_job=types.ModuleType('noark5_workflow.core.job')
        native_store=types.ModuleType('noark5_workflow.core.job_store')
        class FakeStatus:
            READY='Klar'
        class FakeJob:
            def __init__(self,**kwargs):
                self.__dict__.update(kwargs)
        class FakeBatch:
            def __init__(self):self._jobs=[]
            def add(self,item):self._jobs.append(item)
            def jobs(self):return self._jobs
        def fake_save(path,batch,**kwargs):
            self.assertEqual(len(batch.jobs()),1)
            j=batch.jobs()[0]
            self.assertIsNone(j.source_extraction)
            self.assertIsNone(j.source_root)
            self.assertEqual(j.work_operations,work)
            self.assertEqual(j.workflow_ids,[])
            self.assertIn('Ikke klar for kjøring',j.message)
            path.write_text('fake serialized joblist',encoding='utf8')
            return path
        native_job.Job=FakeJob;native_job.JobBatch=FakeBatch;native_job.JobStatus=FakeStatus
        native_store.save_job_list=fake_save
        dest=self.root/'C-drive'/'restored.n5jobs'
        dest.parent.mkdir()
        with patch.dict(sys.modules,{'noark5_workflow.core.job':native_job,
                                     'noark5_workflow.core.job_store':native_store}):
            self.assertEqual(save_recovered_report_jobs(plan,dest),dest)
        self.assertTrue(dest.is_file())

    def test_never_replace_existing_list(self):
        work=self.root/'dwm';add_report(work,'JOB-001','a')
        plan=discover_report_jobs(work)
        dest=self.root/'existing.n5jobs'
        dest.write_text('original',encoding='utf8')
        with self.assertRaises(FileExistsError):
            save_recovered_report_jobs(plan,dest)
        self.assertEqual(dest.read_text(),'original')

    def test_gui_has_discovery_button_and_source_thread_safety(self):
        gui=(Path(__file__).resolve().parents[1]/'gui'/'jobs_window_v017_a2.py').read_text(encoding='utf8')
        self.assertIn('Gjenfinn DWM-jobber',gui)
        self.assertIn('threading.Thread(target=worker',gui)
        self.assertIn('results.put',gui)
        self.assertIn("getattr(self.master, '_load_job_list_file'",gui)


if __name__ == '__main__':
    unittest.main()
