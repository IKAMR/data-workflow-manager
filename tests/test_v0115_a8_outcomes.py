"""a8: report observed statuses, not invented approvals or inferred completeness."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from noark5_workflow.analysis.canonical_outcomes_v0115_a8 import (
    _status, _classify, evaluate_recorded_outcomes,
)
from collections import Counter


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name) / 'work'
        self.work.mkdir()
        self.uid = str(uuid4())
        self.evidence = self.work / 'noark5_evidence'
        self.evidence.mkdir()
        self.profile = Path(tmp.name) / 'control-profile.json'
        self.profile.write_text(json.dumps({
            'model_id': 'noark5.control-profile.v1',
            'profile_id': 'test.draft', 'approved': False,
            'requirements': [
                {'control_id': 'xml_schema', 'requirement': 'required'},
                {'control_id': 'xpath', 'requirement': 'required'},
                {'control_id': 'arkade_noark', 'requirement': 'conditional', 'condition': 'if agreed'},
            ]}), encoding='utf-8')
        validator = patch('noark5_workflow.analysis.canonical_results._validate_work',
                          return_value=(self.work, {'job_uid': self.uid}))
        validator.start()
        self.addCleanup(validator.stop)
        self.save([
            {'source_kind': 'dwm_master', 'test_id': 'kdrs.c02', 'status': 'ok'},
            {'source_kind': 'dwm_raw', 'test_id': 'noark5.xml-schema-validation.v1/arkivstruktur-xsd', 'status': 'ok'},
            {'source_kind': 'dwm_raw', 'test_id': 'arkade5_noark5_test', 'status': 'ok'},
        ])

    def save(self, rows):
        (self.evidence / 'canonical-results.json').write_text(json.dumps({
            'model_id': 'noark5.canonical-results.v1',
            'extraction': {'stable_id': self.uid}, 'observations': rows,
        }), encoding='utf-8')

    def test_raw_ok_never_means_validation_passed(self):
        r = evaluate_recorded_outcomes(self.work, self.profile)
        xml = r['controls'][0]
        self.assertEqual(xml['reported_outcome'], 'execution_recorded_only')
        self.assertEqual(xml['sources'][0]['interpretation'], 'execution_only')
        self.assertFalse(r['summary']['all_required_outcomes_verified'])
        self.assertIsNone(r['summary']['depot_approval'])
        self.assertIsNone(r['summary']['archive_creator_acceptance'])

    def test_master_ok_is_reported_but_unverified(self):
        r = evaluate_recorded_outcomes(self.work, self.profile)
        row = r['controls'][1]
        self.assertEqual(row['reported_outcome'], 'reported_ok_not_verified')
        self.assertIsNone(row['requirement_satisfied'])
        self.assertEqual(row['professional_review'], 'not_verified')

    def test_missing_required_is_visible(self):
        self.save([{'source_kind': 'dwm_master', 'test_id': 'kdrs.c02', 'status': 'ok'}])
        r = evaluate_recorded_outcomes(self.work, self.profile)
        self.assertEqual(r['summary']['required_without_registered_evidence'], ['xml_schema'])
        self.assertEqual(r['controls'][0]['reported_outcome'], 'not_documented')

    def test_failed_and_warning_are_flagged(self):
        self.save([{'source_kind': 'dwm_master', 'test_id': 'kdrs.c02', 'status': 'error'},
                   {'source_kind': 'dwm_master', 'test_id': 'kdrs.c03', 'status': 'warning'}])
        r = evaluate_recorded_outcomes(self.work, self.profile)
        self.assertIn('xpath', r['summary']['controls_flagged_for_review'])
        self.assertEqual(r['controls'][1]['reported_outcome'], 'reported_failure_needs_review')

    def test_unknown_status_is_not_ok(self):
        self.assertEqual(_status('EXOTIC'), 'unknown')
        self.assertEqual(_classify('dwm_master', Counter({'unknown': 1})), 'unresolved')
        self.assertEqual(_status('skipped'), 'not_executed_or_not_applicable')

    def test_quality_assurance_questions_are_not_responses(self):
        r = evaluate_recorded_outcomes(self.work, self.profile)
        preparation = r['quality_assurance_preparation']
        self.assertEqual(preparation['archive_creator_response'], 'not_requested')
        self.assertIsNone(preparation['content_and_provenance_confirmed'])
        self.assertTrue(preparation['open_questions'])

    def test_read_only_and_hashes_preserved(self):
        before = {p.name: p.read_bytes() for p in self.evidence.iterdir()}
        r = evaluate_recorded_outcomes(self.work, self.profile)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.evidence.iterdir()})
        self.assertEqual(len(r['canonical_sha256']), 64)

    def test_unsupported_profile_approval_rejected(self):
        data = json.loads(self.profile.read_text(encoding='utf-8'))
        data['approved'] = True
        self.profile.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'ikke-godkjent'):
            evaluate_recorded_outcomes(self.work, self.profile)


if __name__ == '__main__':
    unittest.main()
