"""Quality assurance draft regression, runnable with an isolated delta."""
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
    module = types.ModuleType('noark5_workflow.analysis.canonical_results')
    module._validate_work = lambda p: (Path(p).resolve(), {'job_uid': 'job-test'})
    sys.modules[module.__name__] = module
    pkg.canonical_results = module
if importlib.util.find_spec('noark5_workflow.analysis.canonical_external_v0115_a5') is None:
    module = types.ModuleType('noark5_workflow.analysis.canonical_external_v0115_a5')
    module.inspect_external = lambda p: {'format': 'unrecognized', 'interpretation': 'not_parsed'}
    sys.modules[module.__name__] = module

from noark5_workflow.analysis.canonical_qa_report_v0115_a12 import (
    build_qa_draft, OUTPUT,
)


class QaReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'noark5_evidence').mkdir()
        self.canonical = self.root / 'noark5_evidence/canonical-results.json'
        self.canonical.write_text(json.dumps({'model_id':'noark5.canonical-results.v1', 'extraction':{'stable_id':'job-test','delivery_id':None}, 'observations':[]}), encoding='utf-8')
        self.profile = self.root / 'control-profile.json'
        self.profile.write_text('{"approved":false}', encoding='utf-8')
        self.matrix = {
            'work_job_uid': 'job-test', 'profile_approved': False,
            'profile_id': 'dwm.noark5.draft.v1',
            'summary': {'required_with_registered_evidence': 2, 'required_categories': 2,
                        'reported_arkade_errors': 2},
            'controls': [{'title': 'Arkade 5 Noark', 'requirement': 'conditional',
                          'assessment': 'reported_errors_require_review',
                          'internal_observations': 1, 'external_test_records': 54}],
        }
        source_path = 'external_evidence/arkade5/r/normalized/arkade5_results.json'
        source = self.root / source_path
        source.parent.mkdir(parents=True)
        source.write_text('{"original":true}', encoding='utf-8')
        self.source = source
        self.analysis = {
            'state': 'linked', 'sources': {source_path: 'analyzed'},
            'analysis': {'sources': [{'evidence': {'work_relative_path': source_path,
                              'sha256': hashlib.sha256(source.read_bytes()).hexdigest()},
                              'analysis': {'source_format': 'arkade_normalized_v2',
                                           'reported_summary': {'system_name': 'ACOS WebSak',
                                                'archival_period': '2005 - 2024', 'archive_type': 'Noark5'},
                                           'records': [
                            {'external_test_id': 'N5.15', 'test_name': 'Mappe',
                             'reported_status': 'error',
                             'reported_result_counts': {'Error': 1},
                             'reported_issues': [{'result_type': 'Error',
                                  'message': '<script>alert(1)</script> Fire mapper under behandling',
                                  'result_set_path': ['Arkivdel: el 4']}]},
                            {'external_test_id': 'N5.22', 'test_name': 'Journalpost',
                             'reported_status': 'error', 'reported_issues': [],
                             'reported_result_counts': {'Error': 1}},
                        ]}}]},
        }
        self.p1 = patch('noark5_workflow.analysis.canonical_qa_report_v0115_a12._validate_work',
                        side_effect=lambda p: (Path(p).resolve(), {'job_uid': 'job-test'}))
        self.p2 = patch('noark5_workflow.analysis.canonical_qa_report_v0115_a12.evaluate_control_matrix',
                        return_value=self.matrix)
        self.p3 = patch('noark5_workflow.analysis.canonical_qa_report_v0115_a12.load_external_status',
                        return_value=self.analysis)
        for p in (self.p1, self.p2, self.p3):
            p.start()
            self.addCleanup(p.stop)

    def test_report_contains_source_specific_errors_and_questions(self):
        result = build_qa_draft(self.root, self.profile, generated_at='2026-11-14T10:00:00Z')
        html = (self.root / OUTPUT).read_text(encoding='utf-8')
        self.assertIn('N5.15', html)
        self.assertIn('N5.22', html)
        self.assertIn('Arkivdel: el 4', html)
        self.assertIn('arkivskaper', html.lower())
        self.assertIn('ACOS WebSak', html)
        self.assertIn('SHA-256', html)
        self.assertEqual(result['summary']['reported_arkade_errors'], 2)
        self.assertEqual(result['summary']['detailed_issue_records'], 2)

    def test_html_escapes_untrusted_external_text(self):
        html = build_qa_draft(self.root, self.profile, write=False)['html']
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_does_not_change_evidence_or_register_approval(self):
        old_source = self.source.read_bytes()
        old_canonical = self.canonical.read_bytes()
        result = build_qa_draft(self.root, self.profile)
        self.assertEqual(self.source.read_bytes(), old_source)
        self.assertEqual(self.canonical.read_bytes(), old_canonical)
        self.assertIsNone(result['archive_creator_acceptance'])
        self.assertIsNone(result['depot_approval'])
        self.assertEqual(result['status'], 'draft_not_approved')

    def test_dry_run_does_not_write(self):
        result = build_qa_draft(self.root, self.profile, write=False)
        self.assertFalse((self.root / OUTPUT).exists())
        self.assertIn('UTKAST', result['html'])

    def test_rejects_approved_or_unrelated_matrix(self):
        for key, value in [('profile_approved', True), ('work_job_uid', 'other-job')]:
            with self.subTest(key=key):
                with patch.dict(self.matrix, {key: value}):
                    with self.assertRaises(ValueError):
                        build_qa_draft(self.root, self.profile)

    def test_refuses_symlink_output(self):
        target = self.root / OUTPUT
        target.parent.mkdir()
        try:
            target.symlink_to(self.source)
        except (OSError, NotImplementedError):
            self.skipTest('symlink not supported')
        with self.assertRaises(ValueError):
            build_qa_draft(self.root, self.profile)
        self.assertEqual(self.source.read_text(), '{"original":true}')

    def test_unlinked_external_does_not_get_published_as_verified(self):
        self.analysis['state'] = 'stale_or_invalid'
        self.analysis['sources'] = {}
        html = build_qa_draft(self.root, self.profile, write=False)['html']
        self.assertNotIn('N5.15', html)
        self.assertIn('Ingen detaljerte', html)


if __name__ == '__main__':
    unittest.main()
