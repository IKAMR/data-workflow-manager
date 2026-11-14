"""a5: job-bound, read-only stage status, trustworthy history and resume."""
from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.production_progress_v020_a5 import (
    STAGE_NAMES, StageEvent, _progress_percent, project_pipeline,
    resume_section, saved_history, stable_job_key,
)
from app.production_review_v020_a4 import ProductionEvidence
from version import VERSION
from tests.version_assertions import assert_release_at_least

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'gui_qt' / 'production_home_v020_a2.py'
GUI = ROOT / 'gui_qt' / 'production_progress_v020_a5.py'


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name) / 'repository_operations'
        self.work.mkdir()
        self.uid = str(uuid4())
        self.job = SimpleNamespace(job_id='JOB-001', name='Testuttrekk',
            status='Klar', operation_count=5, current_operation=0,
            progress=0.0, effective_work_operations=str(self.work))
        self.evidence = ProductionEvidence(
            'JOB-001', 'Testuttrekk', self.work, None, 0, 'Ukjent',
            'Ikke faglig vurdert', 0, None, 0, 'Ingen evidenskandidat funnet', ())

    def projection(self, **kwargs):
        return project_pipeline(self.job, evidence=self.evidence,
                                read_history=False, **kwargs)

    def test_all_eight_areas_keep_order_and_do_not_infer_completed_steps(self):
        progress = self.projection()
        self.assertEqual([stage.key for stage in progress.stages],
                         [key for key, title in STAGE_NAMES])
        states = {stage.key: stage.state for stage in progress.stages}
        self.assertEqual(states['workspace'], 'ready')
        self.assertEqual(states['control'], 'pending')
        self.assertEqual(states['report'], 'pending')
        self.assertEqual(states['preserve'], 'pending')
        self.assertEqual(states['antivirus'], 'unknown')
        self.assertEqual(states['ingest'], 'unknown')
        self.assertEqual(states['crm'], 'unknown')
        self.assertEqual(progress.professional_status, 'Ikke faglig vurdert')

    def test_completed_job_is_not_a_professional_decision(self):
        self.job.status = 'Ferdig'
        self.job.current_operation = 5
        self.job.progress = 1
        progress = self.projection()
        self.assertEqual(progress.stages[3].state, 'done')
        self.assertEqual(progress.stages[4].state, 'pending')
        self.assertEqual(progress.professional_status, 'Ikke faglig vurdert')
        self.assertEqual(progress.operation_percent, 100)

    def test_report_does_not_complete_control_or_depot_approval(self):
        self.evidence = ProductionEvidence(
            'JOB-001', 'Testuttrekk', self.work,
            self.work/'noark5_reports'/'depot_validation_report.json',
            6, 'completed', 'Ikke faglig vurdert', 0, 4, 0,
            'Ingen evidenskandidat funnet', ())
        progress = self.projection()
        self.assertEqual(progress.stages[4].state, 'ready')
        self.assertEqual(progress.stages[3].state, 'partial')
        self.assertIn('Ikke faglig vurdert', progress.stages[4].detail)
        self.assertNotEqual(progress.stages[4].state, 'done')

    def test_manual_decision_does_not_create_aip_or_av_scan(self):
        self.evidence = ProductionEvidence(
            'JOB-001', 'Testuttrekk', self.work, self.work/'depot_validation_report.json',
            7, 'completed', 'Akseptert med avvik', 2, 5, 4,
            'Evidenskandidat funnet \u2013 integritet IKKE kontrollert', ())
        progress = self.projection()
        self.assertEqual(progress.professional_status, 'Akseptert med avvik')
        self.assertEqual(progress.stages[5].state, 'partial')
        self.assertIn('ikke en verifisert DIAS AIP', progress.stages[5].detail)
        self.assertEqual(progress.stages[1].state, 'unknown')

    def test_waiting_failed_running_and_disconnected_work_remain_distinct(self):
        for status, expected in (('Kj\u00f8rer', 'active'),
                                 ('Venter ved kontrollpunkt', 'attention'),
                                 ('Feil', 'attention'),
                                 ('Frakoblet (sist: Ferdig)', 'attention')):
            with self.subTest(status=status):
                self.job.status = status
                self.assertEqual(self.projection().stages[3].state, expected)

    def test_missing_job_and_work_never_read_or_write(self):
        no_job = project_pipeline(None)
        self.assertFalse(no_job.has_job)
        self.assertEqual(len(no_job.stages), 8)
        self.assertEqual(no_job.events, ())
        disconnected = self.evidence.__class__(
            'JOB-001','Test',self.work/'offline',None,0,'Ukjent',
            'Ikke faglig vurdert',0,None,0,'Ikke unders\u00f8kt',())
        self.assertEqual(project_pipeline(self.job,evidence=disconnected,
                           read_history=False).stages[2].state, 'attention')

    def test_percentage_is_only_execution_progress(self):
        for value, expected in ((0,0),(0.5,50),(1,100),(4,100),(-3,0),
                                ('bad',0),(float('inf'),0),(float('nan'),0)):
            with self.subTest(value=value):
                self.assertEqual(_progress_percent(value),expected)

    def test_no_files_are_created_by_projection_or_read_only_history(self):
        before = tuple(sorted(p.relative_to(self.work) for p in self.work.rglob('*')))
        self.projection()
        saved_history(self.work,job_uid=self.uid,job_id='JOB-001')
        after = tuple(sorted(p.relative_to(self.work) for p in self.work.rglob('*')))
        self.assertEqual(before,after)


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name) / 'repository_operations'
        self.work.mkdir()
        self.uid = str(uuid4())
        self.other = str(uuid4())

    def write_jsonl(self, entries):
        (self.work/'job-events.jsonl').write_text(
            '\n'.join(json.dumps(e) for e in entries) + '\n', encoding='utf-8')

    def test_job_events_filter_by_stable_uid_and_assign_stages(self):
        self.write_jsonl([
            {'at':'2026-11-01T10:00:00+01:00','job_uid':self.uid,
             'kind':'work.migrated','detail':'Work registrert'},
            {'at':'2026-11-02T10:00:00+01:00','job_uid':self.uid,
             'kind':'run.finished','detail':'Kontroll gjennomf\u00f8rt'},
            {'at':'2026-11-03T10:00:00+01:00','job_uid':self.other,
             'kind':'run.error','detail':'ANNEN JOBB'},
        ])
        events = saved_history(self.work,job_uid=self.uid,job_id='JOB-001')
        self.assertEqual(len(events),2)
        self.assertEqual([e.stage for e in events],['control','workspace'])
        self.assertNotIn('ANNEN JOBB',' '.join(e.detail for e in events))

    def test_same_job_number_other_uid_in_run_log_is_ignored(self):
        folder = self.work/'run_logs'/'JOB-001'
        folder.mkdir(parents=True)
        for suffix,uid in ((1,self.uid),(2,self.other)):
            run_id=f'20261101T10000{suffix}Z-12345678'
            (folder/(run_id+'.json')).write_text(json.dumps({
                'job_id':'JOB-001','run_id':run_id,'job_uid':uid,
                'run_kind':'workflow','status':'finished','started_at':'2026-11-01T10:00:00Z',
            }),encoding='utf-8')
        events=saved_history(self.work,job_uid=self.uid,job_id='JOB-001')
        self.assertEqual(len(events),1)
        self.assertEqual(events[0].kind,'Kj\u00f8relogg: finished')

    def test_run_history_follows_verified_work_alias_after_job_renumber(self):
        folder = self.work/'run_logs'/'JOB-001'
        folder.mkdir(parents=True)
        run_id = '20261101T101010Z-12345678'
        (folder/(run_id+'.json')).write_text(json.dumps({
            'job_id':'JOB-001','run_id':run_id,'job_uid':self.uid,
            'run_kind':'workflow','status':'finished','started_at':'2026-11-01T10:10:10Z',
        }),encoding='utf-8')
        definition = self.work/'job.json'
        definition.write_text(json.dumps({
            'file_type':'dwm-work-job','job_uid':self.uid,
            'job_list_aliases':['JOB-001','JOB-002'],
        }),encoding='utf-8')
        history = saved_history(self.work,job_uid=self.uid,job_id='JOB-002')
        self.assertEqual(len(history),1)
        definition.write_text(json.dumps({
            'file_type':'dwm-work-job','job_uid':self.other,
            'job_list_aliases':['JOB-001','JOB-002'],
        }),encoding='utf-8')
        self.assertEqual(saved_history(self.work,job_uid=self.uid,job_id='JOB-002'),())

    def test_invalid_and_symlinked_event_files_not_trusted(self):
        events_path = self.work/'job-events.jsonl'
        events_path.write_text('not-json\n{"job_uid":"oops"}\n',encoding='utf-8')
        self.assertEqual(saved_history(self.work,job_uid=self.uid,job_id='JOB-001'),())
        events_path.unlink()
        outside=Path(self.tmp.name)/'outside.txt'
        outside.write_text(json.dumps({'job_uid':self.uid,'kind':'run.finished'}),encoding='utf-8')
        try:
            events_path.symlink_to(outside)
        except (NotImplementedError,OSError):
            self.skipTest('symlink disabled')
        self.assertEqual(saved_history(self.work,job_uid=self.uid,job_id='JOB-001'),())

    def test_without_uid_history_does_not_mix_unrelated_jobs(self):
        self.write_jsonl([{'at':'2026-11-01','job_uid':self.uid,'kind':'run.finished'}])
        self.assertEqual(saved_history(self.work,job_uid='',job_id='JOB-001'),())

    def test_oversized_jsonl_is_bounded_and_broken_tail_is_ignored(self):
        self.write_jsonl([
            {'at':f'2026-11-01T10:{i:02d}:00Z','job_uid':self.uid,
             'kind':'run.finished','detail':'test'} for i in range(50)
        ])
        with (self.work/'job-events.jsonl').open('a',encoding='utf-8') as f:
            f.write('{not a complete json}\n')
        events=saved_history(self.work,job_uid=self.uid,job_id='JOB-001')
        self.assertLessEqual(len(events),35)
        self.assertTrue(events)

    def test_real_report_bound_professional_history_is_visible(self):
        try:
            from noark5_workflow.analysis.depot_assessment import load_depot_assessment
        except ImportError:
            self.skipTest('Full DWM core required to exercise the real assessment loader')
        report = self.work/'noark5_reports'/'depot_validation'/'RUN-1'/'depot_validation_report.json'
        report.parent.mkdir(parents=True)
        report.write_text('{"report_type":"noark5_depot_validation","assessment":{}}',encoding='utf-8')
        decision={'assessed_at':'2026-11-11T12:30:00+01:00',
                  'status':'requires_clarification','reason':'Check',
                  'user':{'user_id':'test'}}
        (report.parent/'depot_assessment.json').write_text(json.dumps({
            'report':{'sha256':hashlib.sha256(report.read_bytes()).hexdigest()},
            'history':[decision], 'current':decision,
        }),encoding='utf-8')
        history=saved_history(self.work,job_uid=self.uid,job_id='JOB-001',report=report)
        self.assertEqual(len(history),1)
        self.assertIn('Krever avklaring',history[0].kind)
        # A changed report must invalidate the decision history.
        report.write_text(report.read_text(encoding='utf-8')+'\n',encoding='utf-8')
        self.assertEqual(saved_history(self.work,job_uid=self.uid,job_id='JOB-001',report=report),())


class DefaultAssessmentLoaderTests(unittest.TestCase):
    def test_reporting_uses_real_default_assessment_loader(self):
        """The regular app path must not call an unbound default loader."""
        import sys
        import types
        from unittest.mock import patch
        from app.production_review_v020_a4 import inspect_production_evidence

        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            report = work / 'depot_validation_report.json'
            report.write_text('{"report_type":"noark5_depot_validation"}', encoding='utf-8')
            job = SimpleNamespace(job_id='JOB-001', name='Test',
                                  effective_work_operations=str(work))
            def discovery(_folder):
                return SimpleNamespace(artifacts=(), warnings=(),
                    depot_report_path=report,
                    depot_report={'report_type':'noark5_depot_validation',
                                  'technical_validation': {'status': 'ok'}})
            package = types.ModuleType('noark5_workflow')
            package.__path__ = []
            analysis = types.ModuleType('noark5_workflow.analysis')
            analysis.__path__ = []
            loader = types.ModuleType('noark5_workflow.analysis.depot_assessment')
            loader.load_depot_assessment = lambda _path: {
                'current': {'status': 'requires_clarification'},
                'history': [{'status': 'requires_clarification'}],
            }
            with patch.dict(sys.modules, {
                    'noark5_workflow': package, 'noark5_workflow.analysis': analysis,
                    'noark5_workflow.analysis.depot_assessment': loader}):
                result = inspect_production_evidence(
                    job, discovery=discovery, load_parts=lambda _path: None,
                    assessment_labels={'requires_clarification':'Krever avklaring'},
                )
            self.assertEqual(result.professional_status, 'Krever avklaring')
            self.assertEqual(result.professional_history, 1)


class ResumeTests(unittest.TestCase):
    def test_same_job_stable_uid_across_joblist_and_local_job_number_changes(self):
        uid = str(uuid4())
        one=stable_job_key('JOB-001',job_uid=uid,job_list_path='C:/a.n5jobs')
        two=stable_job_key('JOB-002',job_uid=uid,job_list_path='D:/other.n5jobs')
        self.assertEqual(one,two)
        self.assertEqual(resume_section(current_key=one,stored_key=two,
                           stored_section='report'),'report')

    def test_other_job_is_never_resumed_by_reused_job_number(self):
        left=stable_job_key('JOB-001',job_list_path='C:/one.n5jobs')
        right=stable_job_key('JOB-001',job_list_path='C:/two.n5jobs')
        self.assertNotEqual(left,right)
        self.assertEqual(resume_section(current_key=right,stored_key=left,
                           stored_section='preserve'),'')

    def test_unsaved_draft_has_no_resume_identity(self):
        self.assertEqual(stable_job_key('JOB-001'),'')
        self.assertEqual(resume_section(current_key='',stored_key='',
                           stored_section='control'),'')

    def test_unknown_and_unavailable_areas_cannot_be_resumed(self):
        key=stable_job_key('JOB-001',job_list_path='c:/jobs.n5jobs')
        for area in ('crm','access','../../evil','', 'progress'):
            self.assertEqual(resume_section(current_key=key,stored_key=key,
                             stored_section=area),'')
        self.assertEqual(resume_section(current_key=key,stored_key=key,
                         stored_section='workspace'),'workspace')


class GUIContractTests(unittest.TestCase):
    def test_status_page_integrated_without_new_runner_or_approval(self):
        source=HOME.read_text(encoding='utf-8')
        gui=GUI.read_text(encoding='utf-8')
        self.assertIn('ProductionProgressPage(window)',source)
        self.assertIn('window.v020_show_progress_page = show_progress',source)
        self.assertIn('window.v020_resume_area = resume_area',source)
        self.assertIn('saved_section_for_window(window)',source)
        self.assertIn('remember_area(\'report\')',source)
        self.assertIn('remember_area(\'preserve\')',source)
        self.assertIn('window.v020_show_control_page()',source)
        self.assertIn('project_pipeline(job, evidence=evidence, job_uid=uid)',gui)
        for forbidden in ('create_grouped_ingest(', 'record_depot_assessment(',
                          'run_job(', 'prepare_candidate('):
            self.assertNotIn(forbidden,source+gui)

    def test_pure_projection_does_not_depend_on_qt(self):
        filename=ROOT/'app'/'production_progress_v020_a5.py'
        src=filename.read_text(encoding='utf-8')
        self.assertNotIn('PySide6',src)
        self.assertNotIn('.mkdir(',src)
        self.assertNotIn('.write_text(',src)
        self.assertNotIn('os.replace(',src)

    def test_release_version_matches_distribution(self):
        assert_release_at_least(self, f'VERSION = "{VERSION}"', "0.2.0", 5)
        with (ROOT/'pyproject.toml').open('rb') as f:
            self.assertEqual(tomllib.load(f)['project']['version'], VERSION.replace('-',''))


if __name__=='__main__':
    unittest.main()
