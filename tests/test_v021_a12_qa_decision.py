"""v0.2.1-a12: two evidence-bound HTML drafts, no automatic acceptance."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from noark5_workflow.reporting.qa_decision_v021_a12 import (
    MODEL, FILES, ReportInputError, build_snapshot, publish, render_reports, main,
)


def digest(p):
    return sha256(p.read_bytes()).hexdigest()


class A12Reports(unittest.TestCase):
    def setUp(self):
        t=TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.work=self.root/'work';self.work.mkdir()
        self.output=self.root/'output';self.output.mkdir()
        self.uid='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        self.run='JOB-001__20261113T003659Z-abc123'
        self.repo=self.work/('noark5_reports/depot_validation/'+self.run+'/depot_validation_report.json')
        self.ref='noark5_tests/xpath/'+self.run+'/index.json'
        self.index=self.put(self.ref, {'execution_profile':'normal','tests':[{'test_id':'kdrs.c01','status':'ok'}]})
        self.master=self.put('noark5_tests/xpath/'+self.run+'/master-results.json', {'source':'a12 sample'})
        self.put('job.json',{'file_type':'dwm-work-job','job_uid':self.uid,
                            'job':{'job_id':'JOB-001','job_uid':self.uid,'name':'1525_004',
                                   'source_extraction':'C:\\archive\\content',
                                   'source_root':str(self.root/'source')}})
        self.canonical=self.put('noark5_evidence/canonical-results.json', {
            'model_id':'noark5.canonical-results.v1','extraction':{'stable_id':self.uid,'noark_version':None},
            'sources':[{'source_kind':'dwm_master','reference':{
                'work_relative_path':'noark5_tests/xpath/'+self.run+'/master-results.json',
                'sha256':digest(self.master)}}], 'observations':[],
        })
        self.arkrel='external_evidence/arkade5/one/normalized/arkade5_results.json'
        self.ark=self.put(self.arkrel,{'source':'external'})
        self.ext=self.put('noark5_evidence/canonical-external-analysis.json', {
            'model_id':'noark5.external-analysis.v1','extraction_stable_id':self.uid,
            'canonical_reference':{'work_relative_path':'noark5_evidence/canonical-results.json',
                                   'sha256':digest(self.canonical)},
            'sources':[{'evidence':{'work_relative_path':self.arkrel,'sha256':digest(self.ark)},
                        'analysis':{'source_format':'arkade_normalized_v2',
                          'reported_summary':{'system_name':'ACOS & samarbeid','number_of_tests_run':'54 av 54',
                            'number_of_errors':'2','number_of_warnings':'0'},
                          'records':[{'external_test_id':'N5.15','reported_status':'error',
                              'reported_issues':[{'result_type':'Error',
                                   'message':'<script>alert(1)</script> Fire mapper under behandling',
                                   'result_set_path':['Arkivdel 4'],
                                   'location':{'file_name':'arkivstruktur.xml','line_numbers':[57,58]}}]},
                              {'external_test_id':'N5.22','reported_status':'error',
                               'reported_issues':[{'result_type':'Error','message':'Journalstatus: Journalført 20',
                               'result_set_path':['Arkivdel 4']}]}]}}]})
        self.put('noark5_evidence/canonical-context.json',{
            'extraction_stable_id':self.uid,
            'canonical_reference':{'sha256':digest(self.canonical)},
            'assessments':[{'event_id':'e1','test_id':'kdrs.c02','metadata_id':'M300',
                            'decision':'needs_follow_up','note':'M300 status krever kontroll',
                            'human_verification':'not_recorded'}]})
        self.depot=self.put(self.repo.relative_to(self.work),{
            'report_type':'noark5_depot_validation',
            'summary':{'archive_part_count':2,'folder_count':132,'registration_count':467,
                       'document_object_count':678},
            'technical_validation':{'status':'ok','summary':{'ok':58,'error':0}},
            'archive_parts':[
              {'archive_part':{'system_id':'part-1','title':'Papir','status':'Avsluttet periode'},
               'folder_count':20,'registration_count':133,'document_object_count':196},
              {'archive_part':{'system_id':'part-2','title':'El 4','status':'Aktiv periode'},
               'folder_count':5,'registration_count':20,'document_object_count':40}],
            'deviations':[{'category':'period_source_divergence','severity':'review',
                           'requires_review':True,'summary':'Perioden trenger avklaring'}],
            'evidence':{'source_xpath_run':'C:\\historic\\noark5_tests\\xpath\\'+self.run},
        })
        self.kdrs=self.root/'kdrs-qa.json'
        self.kdrs.write_text(json.dumps({
            'report_type':'noark5_a11_practical_kdrs_qa_not_full_parity',
            'preflight':{'dwm_index_sha256':digest(self.index)},
            'comparison_summary':{'rows':50,'provisional_matches':29,
                                  'provisional_mismatches':0,'not_comparable':21},
            'historical_execution_time_xml_sha256_attested':False,
        }),encoding='utf8')

    def put(self,relative,value):
        p=self.work/relative;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value,ensure_ascii=False),encoding='utf8');return p

    def build(self, **kw):
        return build_snapshot(work=self.work,kdrs_qa=self.kdrs,created_at='2026-11-15T22:00:00+01:00',**kw)

    def test_realistic_extraction_label_not_generic_content(self):
        from noark5_workflow.reporting.qa_decision_v021_a12 import _extraction_label
        j={'name':'content','source_extraction':
           r'I:\arkiv-noark5\1525\1525_004_E-1525-2025-0001\content\sip\content'}
        self.assertEqual(_extraction_label(j),'1525_004_E-1525-2025-0001')
        self.assertEqual(_extraction_label({'name':'content', 'source_root':r'D:\sip\content'}),
                         'Ikke dokumentert')
        self.assertEqual(_extraction_label({'name':'1525_004', 'source_root':r'D:\sip\content'}),
                         '1525_004')

    def test_two_distinct_reports_and_unapproved_status(self):
        result=self.build()
        self.assertEqual(result['model_id'],MODEL)
        self.assertTrue(result['review_required'])
        self.assertFalse(result['acceptance_from_archive_creator_registered'])
        self.assertFalse(result['depot_formal_decision_registered_by_a12'])
        self.assertFalse(result['aip_produced_by_a12'])
        self.assertEqual(len(result['archive_parts']),2)
        self.assertEqual(len(result['arkade']['findings']),2)
        self.assertEqual(len(result['findings']),4)  # one DWM, two Arkade, one active part
        self.assertEqual(result['kdrs_qa']['summary']['provisional_matches'],29)
        html=render_reports(result)
        public=html['01-kvalitetssikring-arkivskaper.html']
        internal=html['02-depot-godkjenning-ferdigstilling.html']
        self.assertIn('Spørsmål til arkivskaper',public)
        self.assertIn('Depotets beslutningsfelt',internal)
        self.assertIn('N5.15',public)
        self.assertIn('N5.22',public)
        self.assertIn('M300',public)
        self.assertIn('Aktiv periode',internal)
        self.assertIn('29',public)
        self.assertNotIn('<script>',public)
        self.assertIn('&lt;script&gt;',public)
        self.assertIn('UTKAST',public)
        self.assertIn('UTKAST',internal)
        self.assertNotIn('godkjent av depot',internal.lower())

    def test_package_is_atomic_non_overwriting_and_inputs_unchanged(self):
        before={p:digest(p) for p in (self.canonical,self.ext,self.ark,self.depot,self.kdrs,self.index)}
        out=publish(self.build(),self.output/'reports',work=self.work)
        self.assertEqual({p.name for p in out.iterdir()},set(FILES))
        m=json.loads((out/'evidensmanifest.json').read_text(encoding='utf8'))
        self.assertEqual(m['job_uid'],self.uid)
        for file,hashval in m['published_files'].items():
            self.assertEqual(digest(out/file),hashval)
        self.assertTrue((out/'funn.csv').read_bytes().startswith(b'\xef\xbb\xbf'))
        self.assertEqual(before,{p:digest(p) for p in before})
        with self.assertRaises(FileExistsError):publish(self.build(),out,work=self.work)
        self.assertFalse(any(p.name.startswith('.a12-staging-') for p in self.output.iterdir()))

    def test_canonical_job_binding_rejects_wrong_job(self):
        j=json.loads(self.canonical.read_text());j['extraction']['stable_id']='other'
        self.canonical.write_text(json.dumps(j))
        with self.assertRaisesRegex(ReportInputError,'annen jobb'):self.build()

    def test_stale_arkade_hash_fails_closed(self):
        self.ark.write_text('{"changed":true}')
        with self.assertRaisesRegex(ReportInputError,'SHA-256'):self.build()

    def test_stale_kdrs_index_fails_closed(self):
        self.index.write_text('{"changed":true}')
        with self.assertRaisesRegex(ReportInputError,'SHA-256'):self.build()

    def test_no_kdrs_is_not_zero_and_still_draft(self):
        result=build_snapshot(work=self.work)
        self.assertEqual(result['kdrs_qa']['status'],'not_selected')
        self.assertIsNone(result['kdrs_qa']['summary'])
        self.assertFalse(result['depot_formal_decision_registered_by_a12'])

    def test_optional_arkade_missing_is_explicit(self):
        self.ext.unlink()
        result=build_snapshot(work=self.work)
        self.assertEqual(result['arkade']['status'],'not_available')
        self.assertIsNone(result['arkade']['test_count'])

    def test_duplicate_depot_reports_require_explicit_selection(self):
        second=self.work/'noark5_reports/depot_validation/JOB-002__extra/depot_validation_report.json'
        second.parent.mkdir(parents=True);second.write_bytes(self.depot.read_bytes())
        with self.assertRaisesRegex(ReportInputError,'nøyaktig én'):self.build()
        selected=self.depot.relative_to(self.work).as_posix()
        result=self.build(depot_report=selected)
        self.assertEqual(result['dwm_report_source'],selected)

    def test_duplicate_external_arkade_requires_explicit_source(self):
        d=json.loads(self.ext.read_text())
        second=json.loads(json.dumps(d['sources'][0]))
        newrel='external_evidence/arkade5/two/normalized/arkade5_results.json'
        other=self.put(newrel,{'source':'second'})
        second['evidence']={'work_relative_path':newrel,'sha256':digest(other)}
        d['sources'].append(second);self.ext.write_text(json.dumps(d))
        with self.assertRaisesRegex(ReportInputError,'Flere Arkade'):self.build()
        out=self.build(arkade_evidence=self.arkrel)
        self.assertEqual(out['arkade']['test_count'],2)

    def test_path_traversal_or_symlink_rejected(self):
        with self.assertRaises(ReportInputError):self.build(depot_report='../../outside.json')
        dest=self.work/'noark5_evidence/link.json'
        try:dest.symlink_to(self.root/'kdrs-qa.json')
        except (OSError,NotImplementedError):self.skipTest('Symlink unsupported')
        from noark5_workflow.reporting.qa_decision_v021_a12 import _source
        with self.assertRaisesRegex(ReportInputError,'Symbolsk lenke'):
            _source(self.work,'noark5_evidence/link.json')

    def test_output_protects_input_and_source(self):
        snapshot=self.build()
        for path in (self.work/'noark5_evidence/new',self.work/'noark5_tests/new',
                     self.work/'noark5_reports/depot_validation/new',self.root/'source'/'new'):
            with self.subTest(path=path),self.assertRaises(ReportInputError):
                publish(snapshot,path,work=self.work)

    def test_depot_assessment_bound_to_exact_report_hash(self):
        rel=self.depot.parent.relative_to(self.work)/'depot_assessment.json'
        assess=self.put(rel,{'report':{'sha256':digest(self.depot)},
                             'current':{'status':'accepted','reason':'Manually assessed'},'history':[{}]})
        result=self.build()
        self.assertEqual(result['existing_depot_assessment']['current']['status'],'accepted')
        self.assertFalse(result['depot_formal_decision_registered_by_a12'])
        d=json.loads(assess.read_text());d['report']['sha256']='1'*64;assess.write_text(json.dumps(d))
        with self.assertRaisesRegex(ReportInputError,'annen versjon'):self.build()

    def test_report_rejects_depot_from_other_run(self):
        value=json.loads(self.depot.read_text())
        value['evidence']['source_xpath_run']='C:\\old\\xpath\\JOB-002__20261113T003659Z-abc123'
        self.depot.write_text(json.dumps(value))
        with self.assertRaisesRegex(ReportInputError,'XPath-kjøring'):self.build()

    def test_csv_escapes_excel_formula_in_external_message(self):
        from noark5_workflow.reporting.qa_decision_v021_a12 import _csv
        state=self.build()
        state['findings'][1]['message']='=HYPERLINK("http://invalid", "click")'
        data=_csv(state).decode('utf-8-sig')
        self.assertIn("'=HYPERLINK",data)

    def test_version_and_distribution_agree(self):
        from version import VERSION
        self.assertRegex(VERSION, r'^0\.2\.1-a[0-9]+$')
        pyproject=(Path(__file__).resolve().parents[1]/'pyproject.toml').read_text()
        self.assertIn('version = "' + VERSION.replace('-a', 'a') + '"', pyproject)

    def test_cli_preflight_writes_nothing_and_cli_writes_reports(self):
        from contextlib import redirect_stdout
        from io import StringIO
        args=['--work',str(self.work),'--kdrs-qa',str(self.kdrs)]
        with redirect_stdout(StringIO()) as printed:
            self.assertEqual(main(args+['--preflight']),0)
        self.assertIn('"depot_approved_by_a12": false',printed.getvalue())
        self.assertFalse((self.output/'reports').exists())
        with redirect_stdout(StringIO()):
            self.assertEqual(main(args+['--output-dir',str(self.output/'reports')]),0)
        self.assertTrue((self.output/'reports/index.html').is_file())

if __name__ == '__main__':unittest.main()
