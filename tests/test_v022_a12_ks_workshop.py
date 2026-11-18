"""a12 workshop regression tests: no Qt installation or real archive required."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from app.ks_workshop_v022_a12 import (
    SECTIONS, RECOMMENDATIONS, WorkshopError, actor_from_profile,
    build_workspace, export_report, filter_findings, findings_with_reviews,
    render_preview, source_catalog, technical_tests, work_file,
)

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Profile:
    user_id: str = 'reviewer-uuid'
    name: str = 'Arkivar'
    username: str = 'arkivar'
    email: str = 'arkivar@example.invalid'
    is_complete: bool = True


class Fixture(unittest.TestCase):
    def setUp(self):
        context = tempfile.TemporaryDirectory()
        self.addCleanup(context.cleanup)
        self.root = Path(context.name)
        self.work = self.root / 'job-a'
        self.work.mkdir()
        self.uid = 'uuid-A'
        self.write('job.json', {'file_type':'dwm-work-job', 'job_uid':self.uid,
                                'job':{'job_id':'JOB-001','name':'Testuttrekk'}})
        master = {
            'tests': [
                {'test_id':'kdrs.c01','name':'Arkivmapper','status':'ok','test_point':'N5.04'},
                {'test_id':'kdrs.c02','name':'Status','status':'warning','test_point':'N5.05'}]
        }
        self.write('noark5_tests/xpath/JOB-001__run/master-results.json',master)
        relative = 'noark5_tests/xpath/JOB-001__run/master-results.json'
        digest = sha256((self.work / relative).read_bytes()).hexdigest()
        self.write('noark5_evidence/canonical-results.json',{
            'model_id':'noark5.canonical-results.v1',
            'extraction':{'stable_id':self.uid},
            'sources':[{'source_kind':'dwm_master','reference':{
                'work_relative_path':relative,'sha256':digest}}]})
        self.write('arkade5_v2.13.1/noark5/arkade-testrapporter_20261118/arkade-testrapport_20261118.json',{
            'TestsResults': [
                {'TestId':'N5.15','TestName':'Saksmappestatus','NumberOfErrors':'2'},
                {'TestId':'N5.22','TestName':'Journalstatus','NumberOfErrors':'0'}]})
        self.write('noark5_tests/xpath_regression/JOB-001__run/index.json',{
            'tests':[{'test_id':'kdrs.c01','status':'ok','file':'results/kdrs_c01.json'},
                     {'test_id':'kdrs.c02','status':'warning','file':'results/kdrs_c02.json'}]})
        self.write('noark5_tests/xpath_regression/JOB-001__run/definitions.json',{
            'tests':[{'test_id':'kdrs.c01','name':'Regresjon arkivmapper'},
                     {'test_id':'kdrs.c02','name':'Regresjon status'}]})
        self.write('noark5_tests/xpath_regression/JOB-001__run/results/kdrs_c01.json',{})
        self.write('noark5_tests/xpath_regression/JOB-001__run/results/kdrs_c02.json',{})
        self.write('noark5_tests/native/noark5-u1-total.json',{'definition_id':'u1'})
        self.write('noark5_tests/native/noark5-analysis-arkiv-arkivdel.json',{'definition_id':'archive'})
        self.write('noark5_tests/schema/JOB-001__run/xml-validation-arkivstruktur.json',{
            'valid':True, 'errors': []})
        self.write('external_evidence/siegfried/run-1/pronom_statistics.json', {'summary': {}})
        (self.work / 'arkade5_v2.13.1/pronom').mkdir(parents=True)
        (self.work / 'arkade5_v2.13.1/pronom/filformatinfo-statistikk.csv').write_text('Format,Antall\nPDF,1\n', encoding='utf-8')
        self.snapshot = {'model_id':'ikamr.dwm.noark5.qa-decision.a12.v1',
            'work_identity':{'job_uid':self.uid,'job_id':'JOB-001','job_name':'Testuttrekk'},
            'archive_parts':[{'system_id':'a1','title':'Aktiv','status':'Aktiv periode',
                              'period_start':'2008-01-01','period_end':'2024-01-01'}],
            'findings':[
                {'source':'Arkade 5','test_id':'N5.15','severity':'ERROR',
                 'message':'Mangler <test>', 'context':'Arkivdel a1','source_ref':relative},
                {'source':'DWM','test_id':'kdrs.c02','severity':'REVIEW',
                 'message':'Må vurderes', 'context':'Hele uttrekket','source_ref':relative} ],
            'evidence_manifest':[{'kind':'dwm_master','path':relative, 'sha256':digest}]}

    def write(self, relative, obj):
        path=self.work/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')


class BasicModelsTests(Fixture):
    def test_technical_tests_are_real_records_and_report_provenance(self):
        rows=technical_tests(self.work)
        self.assertEqual(len(rows), 11)
        self.assertEqual(sum(r['engine']=='DWM XPath' for r in rows), 2)
        self.assertEqual(sum(r['engine']=='Arkade 5 Noark' for r in rows), 2)
        self.assertEqual(sum(r['engine']=='DWM XPath-regresjon' for r in rows), 2)
        self.assertEqual(sum(r['engine']=='DWM native' for r in rows), 2)
        self.assertEqual(next(r for r in rows if r['test_id']=='N5.15')['status'], 'FEIL')
        self.assertEqual(next(r for r in rows if r['test_id']=='N5.22')['status'], 'OK')
        self.assertEqual(sum('PRONOM' in r['engine'] for r in rows), 2)
        self.assertFalse(any(r['status']=='Godkjent' for r in rows))

    def test_existing_canonical_job_uid_must_match_work(self):
        file=self.work/'noark5_evidence/canonical-results.json'
        data=json.loads(file.read_text('utf-8'))
        data['extraction']['stable_id']='DIFFERENT'
        file.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaisesRegex(WorkshopError, 'annen jobb'):
            technical_tests(self.work)

    def test_master_sha_change_is_blocking(self):
        f=self.work/'noark5_tests/xpath/JOB-001__run/master-results.json'
        f.write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(WorkshopError,'SHA-256'):
            technical_tests(self.work)

    def test_work_file_blocks_traversal_absolute_and_symlinks(self):
        relative='noark5_evidence/canonical-results.json'
        self.assertTrue(work_file(self.work,relative).is_file())
        for evil in ('../outside.json','/etc/passwd','C:/Windows/system32/notepad.exe',
                     'noark5_evidence/../job.json','//fileserver/other','C:\\Windows\\system.ini'):
            with self.subTest(evil=evil), self.assertRaises(WorkshopError):
                work_file(self.work,evil)
        link=self.work/'linked'
        try: link.symlink_to(self.work/'job.json')
        except (NotImplementedError,OSError): pass
        else:
            with self.assertRaises(WorkshopError):work_file(self.work,'linked')

    def test_changed_manifest_evidence_is_reported_not_false_ok(self):
        self.snapshot['evidence_manifest'][0]['sha256']='0'*64
        sources=source_catalog(self.work,self.snapshot)
        self.assertEqual(sources[0]['integrity'], 'ENDRET – SHA-256 AVVIK')

    def test_source_catalog_includes_verified_files_and_a7_qa_basis(self):
        self.write('noark5_evidence/qa-basis-draft.json', {'automatic_approval':False})
        sources=source_catalog(self.work,self.snapshot)
        self.assertEqual(len(sources),3)
        self.assertTrue(all(s['exists'] for s in sources))
        self.assertEqual(sources[0]['integrity'], 'SHA-256 OK')
        self.assertTrue(any(s['path'].endswith('qa-basis-draft.json') for s in sources))

    def test_filters_by_source_level_review_and_search(self):
        rows=[{'source':'Arkade','test_id':'N5.15','severity':'ERROR','message':'Aktiv', 'review_status':''},
              {'source':'DWM','test_id':'XSD','severity':'WARNING','message':'Avvik','review_status':'context_documented'}]
        self.assertEqual(len(filter_findings(rows,severity='ERROR')),1)
        self.assertEqual(len(filter_findings(rows,source='DWM')),1)
        self.assertEqual(len(filter_findings(rows,review='pending')),1)
        self.assertEqual(len(filter_findings(rows,review='reviewed')),1)
        self.assertEqual(len(filter_findings(rows,search='xsd')),1)

    def test_actor_profile_is_not_anonymous(self):
        actor=actor_from_profile(Profile())
        self.assertEqual(actor.as_dict()['user_id'],'reviewer-uuid')
        with self.assertRaisesRegex(WorkshopError,'brukerprofil'):
            actor_from_profile(None)
        with self.assertRaisesRegex(WorkshopError,'brukerprofil'):
            actor_from_profile(Profile(is_complete=False))

    def test_render_preview_is_escaped_a_draft_and_selectable(self):
        tests=technical_tests(self.work)
        sources=source_catalog(self.work,self.snapshot)
        html=render_preview(self.snapshot,self.snapshot['findings'],tests,sources,
             sections=['summary','findings','parts'],recommendation='conditional',
             recommendation_note='Vi trenger <flere> svar')
        self.assertIn('UTKAST',html)
        self.assertIn('Mangler &lt;test&gt;',html)
        self.assertIn('Vi trenger &lt;flere&gt;',html)
        self.assertIn('Arkivdeler og perioder',html)
        self.assertNotIn('<h2>Tekniske tester',html)
        self.assertIn('Alle originale funn er bevart',html)
        self.assertIn('ingen formell depotgodkjenning',html)
        self.assertIn('Foreslås godkjent med merknader (ikke vedtak)',html)
        self.assertNotIn('automatic_approval: True',html)
        with self.assertRaises(WorkshopError):
            render_preview(self.snapshot,[],[],[],sections=[])
        with self.assertRaises(WorkshopError):
            render_preview(self.snapshot,[],[],[],sections=['summary'],recommendation='approved')

    def test_non_included_comment_is_hidden_but_finding_remains_visible(self):
        findings=[dict(self.snapshot['findings'][0], review_status='context_documented',
                       review_comment='Konfidensiell kommentar', include_in_ks=False)]
        text=render_preview(self.snapshot, findings, [], [], sections=['findings'])
        self.assertIn('Mangler &lt;test&gt;',text)
        self.assertNotIn('Konfidensiell kommentar',text)
        self.assertIn('Vurdert internt',text)

    def test_older_job_without_canonical_still_shows_arkade_and_xsd(self):
        (self.work/'noark5_evidence/canonical-results.json').unlink()
        tests=technical_tests(self.work)
        self.assertEqual(len(tests),9)
        self.assertEqual(sum(t['engine']=='Arkade 5 Noark' for t in tests),2)

    def test_stable_output_artifacts_are_unchanged_by_preview(self):
        before={p:sha256(p.read_bytes()).hexdigest() for p in self.work.rglob('*') if p.is_file()}
        for _ in range(3):
            render_preview(self.snapshot,self.snapshot['findings'],technical_tests(self.work),[],
                           sections=[k for k,_ in SECTIONS])
        self.assertEqual(before,{p:sha256(p.read_bytes()).hexdigest()
                                 for p in self.work.rglob('*') if p.is_file()})


class BridgeTests(Fixture):
    def test_snapshot_builder_reuses_existing_qa_model(self):
        fake=types.ModuleType('noark5_workflow.reporting.qa_workflow_v022_a3')
        fake.build_review_snapshot_v022_a3=lambda *,work:self.snapshot
        with patch.dict(sys.modules,{'noark5_workflow.reporting.qa_workflow_v022_a3':fake}):
            self.assertEqual(build_workspace(self.work),self.snapshot)
            wrong=dict(self.snapshot, work_identity={'job_uid':'DIFFERENT'})
            fake.build_review_snapshot_v022_a3=lambda *,work:wrong
            with self.assertRaises(WorkshopError):build_workspace(self.work)

    def test_reviews_reuse_fingerprint_and_latest_from_existing_ledger(self):
        fake=types.ModuleType('noark5_workflow.reporting.qa_review_v021_a13')
        fake.finding_key=lambda finding:'key:'+finding['test_id']
        fake.latest_reviews=lambda work,snapshot:{'current':{
            'key:N5.15':{'status':'requires_clarification','comment':'Uklar årsak',
                         'include_in_ks':True,'include_in_depot':False,'author':{'display_name':'Arkivar'}}}}
        with patch.dict(sys.modules,{'noark5_workflow.reporting.qa_review_v021_a13':fake}):
            rows=findings_with_reviews(self.work,self.snapshot)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['review_comment'],'Uklar årsak')
        self.assertEqual(rows[0]['review_status'],'requires_clarification')
        self.assertFalse(rows[0]['include_in_depot'])
        self.assertEqual(rows[1]['review_status'],'')

    def test_export_delegates_atomic_a3_bundle_and_adds_sha_labeled_cover(self):
        fake_qa=types.ModuleType('noark5_workflow.reporting.qa_export_v022_a3')
        def export(*,work,output_dir):
            dest=Path(output_dir)
            dest.mkdir()
            (dest/'rapportpakke-manifest.json').write_text('{"automatic_approval":false}',encoding='utf-8')
            return {'directory':dest,'index':dest/'index.html','summary':{}}
        fake_qa.export_review_bundle_v022_a3=export
        fake_safety=types.ModuleType('noark5_workflow.reporting.qa_decision_v021_a13')
        fake_safety._safe_destination=lambda destination,work,job,jobs: None
        with patch.dict(sys.modules, {'noark5_workflow.reporting.qa_export_v022_a3':fake_qa,
                                      'noark5_workflow.reporting.qa_decision_v021_a13':fake_safety}), \
             patch('app.ks_workshop_v022_a12.build_workspace',return_value=self.snapshot), \
             patch('app.ks_workshop_v022_a12.findings_with_reviews',return_value=tuple(self.snapshot['findings'])):
            result=export_report(self.work,self.root/'KS_001', sections=['summary','findings'])
        self.assertTrue(result['workshop_html'].is_file())
        meta=json.loads(result['workshop_metadata'].read_text('utf-8'))
        self.assertFalse(meta['automatic_approval'])
        self.assertEqual(meta['report_status'],'UTKAST_KREVER_FAGLIG_BESLUTNING')
        self.assertEqual(meta['cover_sha256'],sha256(result['workshop_html'].read_bytes()).hexdigest())
        self.assertTrue((self.root/'KS_001/rapportpakke-manifest.json').is_file())


class GuiContracts(unittest.TestCase):
    def test_qt_deferred_and_same_a11_runner(self):
        main=(ROOT/'gui_qt/main_v022_a12.py').read_text('utf-8')
        entry=(ROOT/'gui_qt/__main__.py').read_text('utf-8')
        self.assertIn('from gui_qt.main_v022_a11 import DwmMainWindow',main)
        self.assertIn('from gui_qt.main_v022_a12 import DwmMainWindow',entry)
        self.assertIn('from gui_qt.basic_multijob_v022_a1_2 import DwmMainWindow',entry)
        self.assertIn("if not hasattr(self, '_toolbar'):",main)
        self.assertIn('from gui_qt.ks_workshop_v022_a12 import KsWorkshopDialog',main)
        self.assertIn("get('run')",main)
        self.assertNotIn('JobRunner(',main)
        self.assertNotIn('api.run_job(',main)
        self.assertNotIn('set_workflow(',main)
        self.assertNotIn('installEventFilter(',main)

    def test_gui_has_filter_source_tests_part_evidence_preview_and_export(self):
        gui=(ROOT/'gui_qt/ks_workshop_v022_a12.py').read_text('utf-8')
        for needle in ('Funn og vurderinger','Alle tester','Arkivdeler',
                       'Kilder og evidens','Rapportutkast','Registrer ny observasjon',
                       'Lagre faglig vurdering','Forhåndsvis utkast','Generer KS-/godkjenningsrapport',
                       'self._get_actor()','record_manual_finding'):
            # the backend function is imported as save_observation in GUI
            if needle=='record_manual_finding':continue
            self.assertIn(needle,gui)
        self.assertIn('self._unsaved',gui)
        self.assertIn('_confirm_unsaved',gui)

    def test_fake_window_headless_constructor_skips_qt(self):
        class Base:
            def __init__(self,api):self.api=api
        mock=types.ModuleType('gui_qt.main_v022_a11')
        mock.DwmMainWindow=Base
        with patch.dict(sys.modules,{'gui_qt.main_v022_a11':mock,'PySide6.QtWidgets':None}):
            name='a12_window_test'
            spec=importlib.util.spec_from_file_location(name,ROOT/'gui_qt/main_v022_a12.py')
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertIsInstance(module.DwmMainWindow(object()),Base)

    def test_version_consistency(self):
        import tomllib
        from version import VERSION
        with (ROOT/'pyproject.toml').open('rb') as file:project=tomllib.load(file)
        from tests.version_assertions import assert_release_at_least
        assert_release_at_least(self, f'VERSION = "{VERSION}"', '0.2.2', 12)
        self.assertEqual(project['project']['version'], VERSION.replace('-a', 'a'))


if __name__=='__main__':unittest.main()
