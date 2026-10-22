"""a20.7: regression on the real K18 9-extraction folder naming contract."""
from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from threading import Event
from unittest.mock import patch

from noark5_workflow.reporting.report_job_discovery_a207 import (
    RecoveryCancelled, RecoveryError, discover_available_report_jobs,
    save_available_report_jobs,
)

NAMES = (
    '1535_003_E-Docu-2025-0001_AIC-10',
    '1535_005_E-Docu-2025-0001_AIC-9',
    '1539_007_E-Docu-2025-0001_AIC-11',
    '1543_010_E-Docu-2025-0001_AIC-4',
    '1543_012_E-Docu-2025-0001_AIC-5',
    '1545_005_E-Docu-2025-0001_AIC-3',
    '1547_003_E-Docu-2025-0001_AIC-6',
    '1547_005_E-Docu-2025-0001_AIC-7',
    '1547_007-E-Docu-2025-0001_AIC-8',
)
REPORT = {'summary': {'archive_part_count': 3, 'folder_count': 701},
          'archive_parts': [{'archive_part': {'system_id': 'p-1', 'title': 'Saksarkiv'},
                             'folder_count': 701}]}


def normal_report(work: Path, job_id='JOB-001') -> Path:
    run = work/'noark5_reports'/'depot_validation'/(job_id+'__RUN-20261012-234738-a1234567')
    run.mkdir(parents=True,exist_ok=True)
    output=run/'depot_validation_report.json'
    output.write_text(json.dumps(REPORT),encoding='utf8')
    (run/'artifact_manifest.json').write_text(json.dumps({
        'job_id':job_id,'source_extraction':'G:/arkiv-noark5/1535/1535_005/content'}),encoding='utf8')
    return output


def archived_report(filepath: Path, *, job_id='JOB-001') -> None:
    filepath.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(filepath,mode='w',compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr('dwm/b03/noark5_reports/depot_validation/' +
                         job_id + '__RUN-20261012-090000-abcdef01/depot_validation_report.json',
                         json.dumps(REPORT))
        package.writestr('dwm/b03/noark5_tests/xpath/JOB-001__RUN-1/results/index.json','{}')


class AllExtractionRecoveryTest(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)/'arkiv-noark5'
        self.root.mkdir()
        self.extractions={}
        for name in NAMES:
            extraction=self.root/name[:4]/name
            (extraction/'repository_operations').mkdir(parents=True)
            # Simulate real large content locations without touching XML.
            (extraction/'content'/'sip'/'content').mkdir(parents=True)
            (extraction/'repository_operations'/'analyse').mkdir()
            (extraction/'repository_operations'/'analyse'/
                (name[:8]+'_noark5-xpath-report.txt')).write_text('legacy KDRS Query',encoding='utf8')
            self.extractions[name[:8]]=extraction

    def add_physical_report(self):
        work=self.extractions['1535_005']/'repository_operations'/'dwm'/'b03'
        result=normal_report(work)
        (work/'noark5_tests'/'xpath').mkdir(parents=True)
        (work/'noark5_views').mkdir()
        return result

    def test_k18_root_finds_all_nine_with_one_depot_report(self):
        report=self.add_physical_report()
        (self.root/'K18_v0.1.4-a8_a-nnn.n5jobs').write_text('{}',encoding='utf8')
        (self.extractions['1535_003']/'repository_operations'/'1535_003_v0.1.7-a14-a2_dwm.zip').write_bytes(b'not a zip')
        messages=[]
        plan=discover_available_report_jobs(self.root,on_progress=messages.append)
        self.assertEqual(len(plan.jobs),9)
        self.assertEqual([x.name for x in plan.jobs],list(NAMES))
        self.assertEqual(len({x.job_id for x in plan.jobs}),9)
        self.assertEqual(sum(job.has_report for job in plan.jobs),1)
        self.assertEqual(len(plan.missing_report_extractions),8)
        self.assertTrue(all('Uttrekk' not in p.name for p in (report,)))
        native=next(x for x in plan.jobs if x.name.startswith('1535_005'))
        self.assertEqual(native.job_id,'JOB-001')
        self.assertEqual(native.source_job_id,'JOB-001')
        self.assertEqual(native.report_file,report)
        other=next(x for x in plan.jobs if x.name.startswith('1535_003'))
        self.assertNotEqual(other.job_id,native.job_id)
        self.assertFalse(other.has_report)
        self.assertIsNone(other.work_operations)
        self.assertTrue(messages and messages[-1].startswith('Ferdig: 9 rapportjobber'))
        self.assertEqual(len(plan.existing_job_lists),1)

    def test_legacy_joblist_is_hint_not_workflow_restoration(self):
        filename=self.root/'K18_old.n5jobs'
        payload={'jobs':[
            {'job_id':'JOB-099', 'source_root':str(self.extractions['1547_003']/'content'),
             'workflow_ids':['dangerous-copy'], 'status':'Ferdig'},
            {'job_id':'JOB-100', 'source_root':'G:/arkiv-noark5/9999_999/unrelated'}]}
        filename.write_text(json.dumps(payload),encoding='utf8')
        plan=discover_available_report_jobs(self.root)
        selected=next(x for x in plan.jobs if x.name.startswith('1547_003'))
        self.assertEqual(selected.source_job_id,'JOB-099')
        self.assertEqual(selected.legacy_job_list,filename)
        self.assertFalse(selected.has_report)

    def test_zip_report_is_usable_even_when_job_id_reused(self):
        self.add_physical_report()
        zipped=self.extractions['1535_003']/'repository_operations'/'1535_003_v0.1.7-a14-a2_dwm.zip'
        archived_report(zipped)
        plan=discover_available_report_jobs(self.root)
        self.assertEqual(len(plan.jobs),9)
        self.assertEqual(sum(x.has_report for x in plan.jobs),2)
        physical=next(x for x in plan.jobs if x.name.startswith('1535_005'))
        archive=next(x for x in plan.jobs if x.name.startswith('1535_003'))
        self.assertEqual(physical.job_id,'JOB-001')
        self.assertEqual(archive.job_id,'JOB-002')
        self.assertEqual(archive.source_job_id,'JOB-001')
        self.assertTrue(archive.report_needs_cache)
        self.assertEqual(archive.archive_report_zip,zipped)
        self.assertIn('ZIP',str(archive.evidence))
        self._check_save(plan,archived=True)

    def _check_save(self,plan,*,archived=False):
        old_data=next((j.report_file.read_bytes() for j in plan.jobs if j.report_file),None)
        store=types.ModuleType('noark5_workflow.core.job_store')
        native=types.ModuleType('noark5_workflow.core.job')
        class FakeJob:
            def __init__(self,**kwargs):
                self.__dict__.update(kwargs)
        class FakeBatch:
            def __init__(self):self.all=[]
            def add(self,x):
                if any(y.job_id==x.job_id for y in self.all):raise ValueError('duplicate')
                self.all.append(x)
            def jobs(self):return self.all
        class FakeJobStatus:READY='Klar'
        native.Job=FakeJob;native.JobBatch=FakeBatch;native.JobStatus=FakeJobStatus
        self.saved_jobs=[]
        def fake_save(path,batch,**kwargs):
            self.saved_jobs=list(batch.jobs())
            path.write_text('new native .n5jobs test fixture',encoding='utf8')
            return path
        store.save_job_list=fake_save
        target=self.root.parent/'C'/'reconstructed.n5jobs'
        target.parent.mkdir()
        with patch.dict(sys.modules,{'noark5_workflow.core.job':native,
                                     'noark5_workflow.core.job_store':store}):
            result=save_available_report_jobs(plan,target)
        self.assertEqual(result,target)
        self.assertEqual(len(self.saved_jobs),len(plan.jobs))
        self.assertTrue(all(j.workflow_ids==[] for j in self.saved_jobs))
        self.assertTrue(all(j.source_root is None for j in self.saved_jobs))
        self.assertTrue(all(j.source_extraction is None for j in self.saved_jobs))
        self.assertTrue(all(j.operation_params['__dwm_report_recovery__']['report_only']
                            for j in self.saved_jobs))
        if archived:
            archive_job=next(j for j in self.saved_jobs if j.name.startswith('1535_003'))
            run_folders=list((archive_job.work_operations/'noark5_reports'/'depot_validation').iterdir())
            self.assertEqual(len(run_folders),1)
            self.assertTrue(run_folders[0].name.startswith(archive_job.job_id+'__'))
            cached=json.loads((run_folders[0]/'depot_validation_report.json').read_text(encoding='utf8'))
            self.assertEqual(cached['summary']['folder_count'],701)
            record=json.loads((run_folders[0]/'recovery_source.json').read_text(encoding='utf8'))
            self.assertEqual(record['original_job_id'],'JOB-001')
            self.assertEqual(record['joblist_job_id'],archive_job.job_id)
        if old_data is not None:
            report=next(x.report_file for x in plan.jobs if x.report_file)
            self.assertEqual(report.read_bytes(),old_data)

    def test_all_nine_without_any_depot_report_are_still_report_jobs(self):
        plan=discover_available_report_jobs(self.root)
        self.assertEqual(len(plan.jobs),9)
        self.assertTrue(all(not x.has_report for x in plan.jobs))
        self.assertEqual(len(plan.missing_report_extractions),9)
        self._check_save(plan)

    def test_shared_noark5_archives_are_mapped_by_exact_preservation_number(self):
        self.add_physical_report()
        shared=self.root/'_noark5'
        shared.mkdir()
        archived_report(shared/'1547_005_v0.1.4-a8_dwm.zip')
        archived_report(shared/'1535_003_v0.1.4-a8_dwm.zip')
        archived_report(shared/'9999_777_unrelated_dwm.zip')
        (shared/'1539_nnn_dwm.zip').write_bytes(b'legacy, no unique identity')
        plan=discover_available_report_jobs(self.root)
        self.assertEqual(len(plan.jobs),9)
        self.assertEqual(sum(x.has_report for x in plan.jobs),3)
        self.assertEqual(len(plan.archived_dwm_zips),3)
        mapped=next(x for x in plan.jobs if x.name.startswith('1547_005'))
        self.assertTrue(mapped.archive_report_zip)
        self.assertEqual(mapped.archive_report_zip.parent,shared)
        self.assertFalse(any(x.archive_report_zip and '9999_777' in x.archive_report_zip.name
                             for x in plan.jobs))

    def test_zip_replaced_between_discovery_and_save_is_rejected(self):
        from noark5_workflow.reporting.report_job_discovery_a207 import _materialize_report
        archive=self.extractions['1547_003']/'repository_operations'/'1547_003_old_dwm.zip'
        archived_report(archive)
        plan=discover_available_report_jobs(self.root)
        item=next(x for x in plan.jobs if x.name.startswith('1547_003'))
        self.assertTrue(item.has_report)
        with zipfile.ZipFile(archive,mode='w',compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr(item.archive_report_member,json.dumps({'summary':{'folder_count':99999}}))
        with self.assertRaisesRegex(RecoveryError,'endret siden funnet'):
            _materialize_report(item,self.root.parent/'cache')

    def test_two_active_dwm_reports_with_same_local_id_can_be_combined(self):
        normal_report(self.extractions['1535_005']/'repository_operations'/'dwm'/'b03')
        normal_report(self.extractions['1547_003']/'repository_operations'/'dwm'/'b02')
        plan=discover_available_report_jobs(self.root)
        self.assertEqual(len(plan.jobs),9)
        reports=[r for r in plan.jobs if r.has_report]
        self.assertEqual(len(reports),2)
        self.assertEqual(len({r.job_id for r in plan.jobs}),9)
        self.assertEqual(sorted(r.source_job_id for r in reports),['JOB-001','JOB-001'])
        self.assertEqual(sum(r.report_needs_cache for r in reports),1)
        self._check_save(plan,archived=False)
        recovered=[j for j in self.saved_jobs if j.name.startswith('1547_003')]
        self.assertEqual(len(recovered),1)
        root=recovered[0].work_operations
        self.assertTrue((root/'noark5_reports'/'depot_validation').is_dir())

    def test_scan_dwm_folder_directly(self):
        self.add_physical_report()
        chosen=self.extractions['1535_005']/'repository_operations'/'dwm'/'b03'
        plan=discover_available_report_jobs(chosen)
        self.assertEqual(len(plan.jobs),1)
        self.assertTrue(plan.jobs[0].has_report)
        self.assertEqual(plan.jobs[0].job_id,'JOB-001')

    def test_unreadable_archived_dwm_never_silently_claimed_as_report(self):
        archive=self.extractions['1547_003']/'repository_operations'/'1547_003_old_dwm.zip'
        archive.write_text('not a ZIP',encoding='utf8')
        plan=discover_available_report_jobs(self.root)
        candidate=next(x for x in plan.jobs if x.name.startswith('1547_003'))
        self.assertFalse(candidate.has_report)
        self.assertIn('ZIP',str(candidate.evidence))
        self.assertIn('Kunne ikke lese eldre DWM ZIP',' '.join(plan.warnings))

    def test_save_never_overwrites_existing_file(self):
        plan=discover_available_report_jobs(self.root)
        previous=self.root.parent/'existing.n5jobs'
        previous.write_text('my data',encoding='utf8')
        with self.assertRaises(FileExistsError):
            save_available_report_jobs(plan,previous)
        self.assertEqual(previous.read_text(encoding='utf8'),'my data')

    def test_save_inside_archive_root_is_forbidden(self):
        plan=discover_available_report_jobs(self.root)
        with self.assertRaisesRegex(RecoveryError,'utenfor skannet arkivområde'):
            save_available_report_jobs(plan,self.root/'overwrite.n5jobs')

    def test_cancelled_scan_writes_nothing(self):
        stop=Event();stop.set()
        with self.assertRaises(RecoveryCancelled):
            discover_available_report_jobs(self.root,cancelled=stop)

    def test_does_not_scan_content_or_documents_for_false_reports(self):
        bad=self.extractions['1535_003']/'content'/'sip'/'content'/'dwm'/'b03'
        normal_report(bad,job_id='JOB-989')
        plan=discover_available_report_jobs(self.root)
        self.assertTrue(all(j.source_job_id != 'JOB-989' for j in plan.jobs))


if __name__=='__main__':
    unittest.main()
