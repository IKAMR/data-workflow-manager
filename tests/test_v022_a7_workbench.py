"""a7: API validation, explicit Work backfill and pre-run dependency guard."""
from __future__ import annotations

from enum import Enum
import importlib.util
from pathlib import Path
import sys
from threading import Lock
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
OLD=(
    'metadata_inventory','validate_xml_schema','analyse_arkivstruktur',
    'run_noark5_xpath_tests_2026','arkade5_noark5_test',
    'siegfried_pronom_identification','arkade5_pronom_analysis',
    'import_arkade5_reports','compose_noark5_views','build_noark5_depot_report',
)

class Status(Enum):
    OK='Ferdig'
    READY='Klar'
    FAILED='Feil'
    WAITING='Venter ved kontrollpunkt'

class Job:
    def __init__(self,job_id,status=Status.OK):
        self.job_id=job_id
        self.workflow_ids=list(OLD)
        self.status=status
        self.next_operation_index=len(OLD) if status==Status.OK else 0
        self.progress=1.0 if status==Status.OK else 0.0
        self.message='old result'
    def set_workflow(self,ids):
        self.workflow_ids=list(ids)
        self.next_operation_index=0

class FakeBase:
    def __init__(self):
        self._guard=Lock()
        self._unavailable_work_ids=set()
        self._work_references={'JOB-002':Path('/work/JOB-002/job.json')}
        self.jobs={'JOB-001':Job('JOB-001'),'JOB-002':Job('JOB-002')}
        self._dirty=False
        self.written=[]
        self.events=[]
        self.set_calls=[]
    def _assert_idle(self): pass
    def _require_job(self,jid): return self.jobs[jid]
    def _persist_work_event(self,job,kind,detail):
        self.written.append((job.job_id,kind,detail))
    def _emit(self,event,job): self.events.append((event,job.job_id))
    def job_details(self,jid): return self.jobs[jid]
    def set_workflow(self,jid,ids):
        self.set_calls.append(tuple(ids))
        self.jobs[jid].set_workflow(ids)
        return self.jobs[jid]
    def save_setup(self,changes): return changes


class ApiTests(unittest.TestCase):
    def setUp(self):
        application=ModuleType('app.application_api')
        application.DwmApiError=type('DwmApiError',(ValueError,),{})
        ui=ModuleType('app.ui_start_preferences_v020_a2')
        ui.UI_SETUP_KEYS=()
        ui.validate_ui_preferences=lambda x:x
        base=ModuleType('app.workbench_api_v0111_a2')
        base.DwmWorkbenchAPI=FakeBase
        settings=ModuleType('settings')
        settings.save_config=lambda x:x
        corejob=ModuleType('noark5_workflow.core.job')
        corejob.JobStatus=Status
        self.patcher=patch.dict(sys.modules,{'app.application_api':application,
            'app.ui_start_preferences_v020_a2':ui,
            'app.workbench_api_v0111_a2':base,'settings':settings,
            'noark5_workflow.core.job':corejob})
        self.patcher.start();self.addCleanup(self.patcher.stop)
        spec=importlib.util.spec_from_file_location('a7_api_under_test',
            ROOT/'app/workbench_api_v020_a2.py')
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.api=mod.DwmWorkbenchAPI()

    def test_completed_job_resumes_at_first_postprocessing_operation(self):
        job=self.api.prepare_a7_postprocessing('JOB-002')
        self.assertEqual(len(job.workflow_ids),14)
        self.assertEqual(job.status,Status.READY)
        self.assertEqual(job.next_operation_index,7)
        self.assertEqual(job.workflow_ids[job.next_operation_index],'import_arkade5_reports')
        self.assertEqual(len(self.api.written),1)
        self.assertEqual(self.api.written[0][0],'JOB-002')
        self.assertEqual(self.api.jobs['JOB-001'].status,Status.OK)
        self.assertEqual(len(self.api.jobs['JOB-001'].workflow_ids),10)

    def test_already_new_job_can_be_extended_without_claiming_tests_done(self):
        self.api.jobs['JOB-002']=Job('JOB-002',Status.READY)
        job=self.api.prepare_a7_postprocessing('JOB-002')
        self.assertEqual(job.next_operation_index,0)
        self.assertEqual(job.progress,0.0)

    def test_failed_partial_job_cannot_be_advanced(self):
        self.api.jobs['JOB-002']=Job('JOB-002',Status.FAILED)
        with self.assertRaisesRegex(ValueError,'Kun fullfort'):
            self.api.prepare_a7_postprocessing('JOB-002')
        self.assertEqual(self.api.written,[])

    def test_missing_work_authority_is_rejected(self):
        self.api._work_references={}
        with self.assertRaisesRegex(ValueError,'autoritativ Work'):
            self.api.prepare_a7_postprocessing('JOB-002')

    def test_invalid_proposed_order_rejected_before_api_mutation(self):
        with self.assertRaisesRegex(ValueError,'A200'):
            self.api.set_workflow('JOB-002',
                ('import_arkade5_reports','arkade5_noark5_test'))
        self.assertEqual(self.api.set_calls,[])

    def test_valid_proposed_order_is_saved_through_base_api(self):
        self.api.set_workflow('JOB-002',OLD)
        self.assertEqual(self.api.set_calls[-1],OLD)

class RunnerTests(unittest.TestCase):
    def test_bad_dependency_blocks_before_first_technical_step(self):
        class FakeJobRunner:
            calls=0
            def run(self,*args,**kwargs):
                FakeJobRunner.calls+=1
                return SimpleNamespace(ok=True)
        runner=ModuleType('noark5_workflow.core.job_runner')
        runner.JobRunner=FakeJobRunner
        runner.JobRunOutcome=lambda ok,started:SimpleNamespace(ok=ok,started=started)
        corejob=ModuleType('noark5_workflow.core.job')
        corejob.JobStatus=Status
        with patch.dict(sys.modules,{'noark5_workflow.core.job':corejob,
                                     'noark5_workflow.core.job_runner':runner}):
            spec=importlib.util.spec_from_file_location('a7_runner_under_test',
                ROOT/'noark5_workflow/core/job_runner_a39.py')
            mod=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            job=Job('JOB-002')
            job.workflow_ids=['build_noark5_depot_report','compose_noark5_views']
            logs=[]
            result=mod.A39JobRunner().run(job,log_cb=logs.append)
            self.assertFalse(result.ok)
            self.assertEqual(FakeJobRunner.calls,0)
            self.assertEqual(job.status,Status.FAILED)
            self.assertTrue(any('A250' in line for line in logs))

    def test_selective_postprocessing_is_blocked_until_prerequisites_complete(self):
        class FakeJobRunner:
            calls=0
            def run_operation(self,*args,**kwargs):
                FakeJobRunner.calls+=1
                return SimpleNamespace(ok=True)
        runner=ModuleType('noark5_workflow.core.job_runner')
        runner.JobRunner=FakeJobRunner
        runner.JobRunOutcome=lambda ok,started:SimpleNamespace(ok=ok,started=started)
        corejob=ModuleType('noark5_workflow.core.job')
        corejob.JobStatus=Status
        with patch.dict(sys.modules,{'noark5_workflow.core.job':corejob,
                                     'noark5_workflow.core.job_runner':runner}):
            spec=importlib.util.spec_from_file_location('a7_runner_selective',
                ROOT/'noark5_workflow/core/job_runner_a39.py')
            mod=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            job=Job('JOB-002',Status.READY)
            from app.workflow_dependencies_v022_a7 import ensure_a7_processing
            job.workflow_ids=list(ensure_a7_processing(job.workflow_ids))
            job.next_operation_index=7  # technical tests complete
            logs=[]
            result=mod.A39JobRunner().run_operation(
                job,'audit_noark5_evidence',log_cb=logs.append)
            self.assertFalse(result.ok)
            self.assertEqual(FakeJobRunner.calls,0)
            self.assertTrue(any('A210' in line for line in logs))
            # After A210 and A220 are complete, A230 may run selectively.
            job.next_operation_index=10
            result=mod.A39JobRunner().run_operation(job,'audit_noark5_evidence')
            self.assertTrue(result.ok)
            self.assertEqual(FakeJobRunner.calls,1)

if __name__=='__main__': unittest.main()
