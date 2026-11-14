"""a14: the completion report is a decision worksheet, never an approval."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import noark5_workflow.analysis as pkg
if importlib.util.find_spec('noark5_workflow.analysis.canonical_results') is None:
    stub = types.ModuleType('noark5_workflow.analysis.canonical_results')
    stub._validate_work = lambda p: (Path(p).resolve(), {'job_uid':'job-test'})
    sys.modules[stub.__name__] = stub
    pkg.canonical_results = stub
if importlib.util.find_spec('noark5_workflow.analysis.canonical_external_v0115_a5') is None:
    stub = types.ModuleType('noark5_workflow.analysis.canonical_external_v0115_a5')
    stub.inspect_external = lambda p: {'format':'unrecognized','interpretation':'not_parsed'}
    sys.modules[stub.__name__] = stub
from noark5_workflow.analysis.canonical_completion_v0115_a14 import build_completion_draft, OUTPUT, CompletionDraftError

class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'noark5_reports').mkdir()
        self.qa=self.root/'noark5_reports/QUALITY_ASSURANCE_DRAFT.html'
        self.qa.write_text('KS UTKAST',encoding='utf8')
        self.profile=self.root/'profile.json';self.profile.write_text('{"approved":false}')
        self.matrix={'work_job_uid':'job-test','profile_approved':False,'profile_id':'draft.v1',
          'summary':{'required_with_registered_evidence':2,'required_categories':2},
          'controls':[{'title':'Arkade Noark','requirement':'conditional','assessment':'reported_errors_require_review'}]}
        self.external={'state':'linked','sources':{'a.json':'analyzed'},'analysis':{'sources':[{
          'evidence':{'work_relative_path':'a.json'},'analysis':{
           'source_format':'arkade_normalized_v2','records':[{'external_test_id':'N5.15','reported_status':'error',
             'reported_result_counts':{'Error':1},'reported_issues':[{'result_type':'Error',
             'message':'<script>alert(1)</script>','result_set_path':['Arkivdel el 4']}]}]}}]}}
        self.patches=[
          patch('noark5_workflow.analysis.canonical_completion_v0115_a14._validate_work',side_effect=lambda p:(Path(p).resolve(),{'job_uid':'job-test'})),
          patch('noark5_workflow.analysis.canonical_completion_v0115_a14.evaluate_control_matrix',return_value=self.matrix),
          patch('noark5_workflow.analysis.canonical_completion_v0115_a14.load_external_status',return_value=self.external)]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def test_build_unapproved_and_preserve_qa(self):
        digest=hashlib.sha256(self.qa.read_bytes()).hexdigest()
        result=build_completion_draft(self.root,self.profile,generated_at='2026-11-14T12:00:00+00:00')
        self.assertEqual(result['status'],'draft_not_approved')
        self.assertFalse(result['summary']['approval_registered'])
        self.assertFalse(result['summary']['journal_reference_registered'])
        self.assertEqual(result['summary']['issues'],1)
        html=(self.root/OUTPUT).read_text(encoding='utf8')
        for phrase in ('IKKE GODKJENT','N5.15','Journalpost-ID',digest,'Data Workflow Manager','v0.1.15-a14'):
            self.assertIn(phrase,html)
        self.assertNotIn('<script>',html)
        self.assertEqual(self.qa.read_text(),'KS UTKAST')

    def test_dry_run_does_not_write(self):
        result=build_completion_draft(self.root,self.profile,write=False)
        self.assertIn('N5.15',result['html'])
        self.assertFalse((self.root/OUTPUT).exists())

    def test_missing_qa_is_explicit(self):
        self.qa.unlink()
        result=build_completion_draft(self.root,self.profile,write=False)
        self.assertFalse(result['summary']['has_qa_draft'])
        self.assertIn('KS-rapportutkast mangler',result['html'])

    def test_wrong_job_rejected(self):
        self.matrix['work_job_uid']='other-job'
        with self.assertRaises(CompletionDraftError):build_completion_draft(self.root,self.profile)

    def test_approved_profile_rejected(self):
        self.matrix['profile_approved']=True
        with self.assertRaises(CompletionDraftError):build_completion_draft(self.root,self.profile)

    def test_symlink_output_rejected(self):
        other=self.root/'elsewhere';other.write_text('original')
        try:(self.root/OUTPUT).symlink_to(other)
        except (OSError,NotImplementedError):self.skipTest('symlink unavailable')
        with self.assertRaises(CompletionDraftError):build_completion_draft(self.root,self.profile)
        self.assertEqual(other.read_text(),'original')

if __name__=='__main__':unittest.main()
