"""a20.8: regression for report-only jobs without DWM work directories.

The actual a19 period reader passes work_operations to Path(). Two K18
extractions have no such root; that is not a fatal report input error.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from noark5_workflow.reporting.report_service_a20 import (
    _report_read_jobs, write_report_package,
)
from test_a20_report_service import make_payload, fake_legacy, opts


class A208MissingWorkRegression(unittest.TestCase):
    @staticmethod
    def jobs(root, n=2, missing=(2,)):
        result=[]
        for i in range(1,n+1):
            value=None if i in missing else root / f'work-{i}'
            result.append(SimpleNamespace(
                job_id=f'JOB-{i:03d}',name=f'1535_{i:03d}_ephorte',
                work_operations=value,
                operation_params={'__dwm_report_recovery__':{
                    'report_only':True,
                    'extraction_path':f'G:/arkiv-noark5/1535/1535_{i:03d}',
                    'evidence':['KDRS Query (eldre kildefiler)'] if value is None else ['DWM depotrapport'],
                    'report_file':'' if value is None else f'G:/somewhere/JOB-{i:03d}/report.json'}}))
        return tuple(result)

    def test_missing_root_is_view_only_and_does_not_create_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            jobs=self.jobs(root)
            read,unavailable=_report_read_jobs(jobs,root/'staging')
            self.assertIs(jobs[0],read[0])
            self.assertIsNot(jobs[1],read[1])
            self.assertIsNone(jobs[1].work_operations)
            self.assertEqual(set(unavailable),{'JOB-002'})
            self.assertFalse(read[1].work_operations.exists())
            self.assertFalse((root/'staging').exists())

    def test_1535_two_jobs_full_export_with_path_none_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            jobs=self.jobs(root)
            payload=make_payload(2,missing={2})
            calls=[]
            def legacy(out,read_jobs,options,*,prefix,formats):
                calls.append(tuple(read_jobs))
                # Exactly the a19 failure mode: Path(None) used to fail here.
                for job in read_jobs:
                    path=Path(job.work_operations)
                    self.assertFalse((path/'noark5_reports'/'period_assessments'/
                                      (job.job_id+'.json')).exists())
                return fake_legacy(payload)(out,read_jobs,options,
                                             prefix=prefix,formats=formats)
            destination=root/'output'
            result=write_report_package(destination,jobs,opts(),
                formats=('html','json'),_legacy_export=legacy)
            self.assertTrue(result.is_file())
            self.assertEqual(len(calls),1)
            self.assertIs(calls[0][0],jobs[0])
            self.assertIsNot(calls[0][1],jobs[1])
            self.assertIsNone(jobs[1].work_operations)
            doc=json.loads((destination/'index.json').read_text('utf-8'))
            self.assertEqual(len(doc['jobs']),2)
            self.assertFalse(doc['jobs'][1]['depot_report'])
            self.assertIn('Ingen Work - operations',doc['jobs'][1]['diagnostic'])
            self.assertIsNone(doc['a20_report_snapshot']['jobs'][1]['counts']['folder_count'])
            html=(destination/'index.html').read_text('utf8')
            self.assertIn('Uten komplett DWM-depotrapport',html)
            self.assertNotIn('_work_not_registered',html)
            self.assertFalse((root/'staging').exists())

    def test_k18_nine_jobs_seven_reports_two_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            jobs=self.jobs(root,n=9,missing=(1,3))
            payload=make_payload(9,missing={1,3})
            def writer(out,read_jobs,options,*,prefix,formats):
                self.assertEqual(len(read_jobs),9)
                self.assertEqual(sum(not (job.work_operations and
                                      Path(job.work_operations).exists())
                                      for job in read_jobs),9)
                self.assertTrue(all(job.work_operations is not None for job in read_jobs))
                return fake_legacy(payload)(out,read_jobs,options,
                                             prefix=prefix,formats=formats)
            dest=root/'out'
            write_report_package(dest,jobs,opts(),formats=('html','json','csv'),
                                 _legacy_export=writer)
            doc=json.loads((dest/'index.json').read_text('utf8'))
            self.assertEqual(len(doc['jobs']),9)
            self.assertEqual(len(doc['report_recovery_sources']),9)
            self.assertEqual(sum(not j['depot_report'] for j in doc['jobs']),2)
            self.assertEqual(sum(x['has_depot_report'] for x in
                                 doc['a20_report_snapshot']['jobs']),7)
            self.assertTrue(all(j.work_operations is None for j in
                                (jobs[0],jobs[2])))
            self.assertTrue((dest/'index.csv').is_file())

    def test_unconfigured_regular_job_also_can_be_reported_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            regular=SimpleNamespace(job_id='JOB-001',work_operations=None,
                                    name='ikke_analysert',operation_params={})
            p=make_payload(1,missing={1})
            def writer(directory,jobs,options,*,prefix,formats):
                self.assertEqual(jobs[0].job_id,'JOB-001')
                self.assertIsNotNone(jobs[0].work_operations)
                return fake_legacy(p)(directory,jobs,options,prefix=prefix,formats=formats)
            write_report_package(root/'out',(regular,),opts(),formats=('html','json'),
                                 _legacy_export=writer)
            self.assertIsNone(regular.work_operations)
            doc=json.loads((root/'out'/'index.json').read_text('utf-8'))
            self.assertIn('Ingen Work - operations',doc['jobs'][0]['diagnostic'])


# Keep recovery persistence tested without depending on the complete a19 repo.
# The test below exercises the exact report-only K18 saved-job path contract.
class A208FutureRecoveryWorkArea(unittest.TestCase):
    def test_no_dwm_root_gets_local_only_assessment_location(self):
        import sys
        import types
        from unittest.mock import patch
        from noark5_workflow.reporting.report_job_discovery_a207 import (
            discover_available_report_jobs, save_available_report_jobs,
        )
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'arkiv-noark5'
            ex=root/'1535'/'1535_003_E-Docu-2025-0001_AIC-10'
            (ex/'repository_operations'/'analyse').mkdir(parents=True)
            (ex/'repository_operations'/'analyse'/'1535_003_noark5-xpath-report.txt').write_text('KDRS',encoding='utf8')
            plan=discover_available_report_jobs(root)
            self.assertEqual(len(plan.jobs),1)
            self.assertIsNone(plan.jobs[0].work_operations)
            native=types.ModuleType('noark5_workflow.core.job')
            store=types.ModuleType('noark5_workflow.core.job_store')
            class Job:
                def __init__(self,**data):self.__dict__.update(data)
            class Batch:
                def __init__(self):self.rows=[]
                def add(self,item):self.rows.append(item)
                def jobs(self):return self.rows
            native.Job=Job
            native.JobBatch=Batch
            native.JobStatus=types.SimpleNamespace(READY='Klar')
            collected=[]
            def fake_save(path,batch,**kw):
                collected.extend(batch.jobs())
                Path(path).write_text('placeholder',encoding='utf8')
                return Path(path)
            store.save_job_list=fake_save
            outfile=Path(temp)/'recovered.n5jobs'
            with patch.dict(sys.modules,{
                 'noark5_workflow.core.job':native,
                 'noark5_workflow.core.job_store':store}):
                save_available_report_jobs(plan,outfile)
            self.assertEqual(len(collected),1)
            job=collected[0]
            self.assertEqual(job.work_operations,Path(temp)/'recovered.recovered-dwm'/'JOB-001')
            self.assertFalse(job.work_operations.exists())
            self.assertFalse((ex/'repository_operations'/'dwm').exists())
            state=job.operation_params['__dwm_report_recovery__']
            self.assertFalse(state['report_cache'])
            self.assertIn('rapportjobb',job.message.lower())


if __name__ == '__main__':
    unittest.main()
