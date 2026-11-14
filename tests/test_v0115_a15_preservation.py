"""a15: staging only, never depot approval or a complete AIP."""
import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import noark5_workflow.analysis as pkg
if importlib.util.find_spec('noark5_workflow.analysis.canonical_results') is None:
    stub=types.ModuleType('noark5_workflow.analysis.canonical_results')
    stub._validate_work=lambda p:(Path(p).resolve(),{'job_uid':'job-test'})
    sys.modules[stub.__name__]=stub
    pkg.canonical_results=stub
# The matrix module is from a14, already in the target repo. Stub it if delta-only.
if importlib.util.find_spec('noark5_workflow.analysis.canonical_matrix_v0115_a11') is None:
    stub=types.ModuleType('noark5_workflow.analysis.canonical_matrix_v0115_a11')
    stub.load_external_status=lambda p: {'state':'not_analyzed','sources':{}}
    sys.modules[stub.__name__]=stub
    pkg.canonical_matrix_v0115_a11=stub
from noark5_workflow.analysis.canonical_preservation_v0115_a15 import (
    prepare_candidate,verify_candidate,PackageCandidateError,OUT,INDEX,digest,
)

class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'job.json').write_text('{"job_uid":"job-test"}',encoding='utf8')
        (self.root/'noark5_reports').mkdir()
        (self.root/'noark5_reports/QUALITY_ASSURANCE_DRAFT.html').write_text('KS',encoding='utf8')
        (self.root/'noark5_evidence').mkdir()
        (self.root/'noark5_evidence/canonical-results.json').write_text('{}',encoding='utf8')
        (self.root/'external_evidence/arkade5/run/normalized').mkdir(parents=True)
        self.external='external_evidence/arkade5/run/normalized/arkade5_results.json'
        (self.root/self.external).write_text('{"tests":[]}',encoding='utf8')
        self.info={'state':'linked','sources':{self.external:'analyzed'}}
        self.p1=patch('noark5_workflow.analysis.canonical_preservation_v0115_a15._validate_work',side_effect=lambda p:(Path(p).resolve(),{'job_uid':'job-test'}))
        self.p2=patch('noark5_workflow.analysis.canonical_preservation_v0115_a15.load_external_status',return_value=self.info)
        self.p1.start();self.p2.start();self.addCleanup(self.p1.stop);self.addCleanup(self.p2.stop)
    def test_build_and_verify_without_touching_source(self):
        before=digest(self.root/self.external)
        result=prepare_candidate(self.root,generated_at='2026-11-14T12:00:00+00:00')
        self.assertEqual(result['status'],'candidate_not_approved_not_aip')
        self.assertFalse(result['manifest']['source_included'])
        self.assertFalse(result['manifest']['approval_registered'])
        self.assertEqual(result['files'],4)
        self.assertIn('noark5_reports/COMPLETION_DECISION_DRAFT.html',result['manifest']['missing_sources'])
        self.assertTrue(verify_candidate(self.root)['verified'])
        self.assertEqual(before,digest(self.root/self.external))
        self.assertTrue((self.root/OUT/'payload'/self.external).exists())
    def test_existing_candidate_never_overwritten(self):
        prepare_candidate(self.root)
        original=digest(self.root/OUT/INDEX)
        with self.assertRaises(PackageCandidateError):prepare_candidate(self.root)
        self.assertEqual(original,digest(self.root/OUT/INDEX))
    def test_corruption_detected(self):
        prepare_candidate(self.root)
        (self.root/OUT/'payload'/self.external).write_text('changed')
        result=verify_candidate(self.root)
        self.assertFalse(result['verified'])
        self.assertIn(self.external,result['failed_files'])
    def test_dry_run_no_changes(self):
        report=prepare_candidate(self.root,write=False)
        self.assertEqual(report['files'],4)
        self.assertFalse((self.root/'preservation_staging').exists())
    def test_path_traversal_rejected(self):
        self.info['sources']={'external_evidence/../../secret.json':'analyzed'}
        with self.assertRaises(PackageCandidateError):prepare_candidate(self.root)
    def test_external_not_verified_not_included(self):
        self.info['sources'][self.external]='source_missing_or_changed'
        result=prepare_candidate(self.root)
        self.assertEqual(result['files'],3)
        self.assertTrue(any('ikke verifisert' in x for x in result['manifest']['missing_sources']))
    def test_source_symlink_refused(self):
        try:(self.root/'noark5_evidence/canonical-context.json').symlink_to(self.root/'job.json')
        except (OSError,NotImplementedError):self.skipTest('symlink unsupported')
        report=prepare_candidate(self.root,write=False)
        self.assertIn('noark5_evidence/canonical-context.json',report['manifest']['missing_sources'])

if __name__=='__main__':unittest.main()
