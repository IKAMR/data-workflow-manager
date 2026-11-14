"""A7 regression: draft requirement plans must never assert completion."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from noark5_workflow.analysis.canonical_control_requirements_v0115_a7 import (
    load_control_profile, evaluate_control_profile)


class DraftRequirementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.uid = str(uuid4())
        evidence = self.work / 'noark5_evidence'
        evidence.mkdir()
        self.canonical = evidence / 'canonical-results.json'
        self.profile = self.root / 'profile.json'
        self.write_profile([
            {'control_id': 'xml_schema', 'requirement': 'required'},
            {'control_id': 'xpath', 'requirement': 'required'},
            {'control_id': 'arkade_noark', 'requirement': 'conditional', 'condition': 'only if requested'}])
        self.write_canonical([{'test_id': 'kdrs.c02', 'status': 'ok', 'source_kind': 'dwm_master'}])
        guard = patch('noark5_workflow.analysis.canonical_results._validate_work',
                      return_value=(self.work, {'job_uid': self.uid}))
        guard.start()
        self.addCleanup(guard.stop)

    def write_profile(self, requirements, approved=False):
        self.profile.write_text(json.dumps({'model_id': 'noark5.control-profile.v1',
                       'profile_id': 'test.draft', 'approved': approved,
                       'requirements': requirements}), encoding='utf-8')

    def write_canonical(self, observations):
        self.canonical.write_text(json.dumps({'model_id': 'noark5.canonical-results.v1',
            'extraction': {'stable_id': self.uid}, 'observations': observations}), encoding='utf-8')

    def test_distinguishes_missing_from_unverified(self):
        r = evaluate_control_profile(self.work, self.profile)
        self.assertEqual(r['summary']['required_categories'], 2)
        self.assertEqual(r['summary']['required_without_registered_evidence'], ['xml_schema'])
        self.assertEqual(r['summary']['required_with_registered_evidence'], 1)
        self.assertIsNone(r['summary']['coverage_complete'])
        self.assertFalse(r['summary']['archive_approved'])
        self.assertFalse(r['summary']['requirements_verified'])
        self.assertEqual(r['controls'][1]['evidence_state'], 'registered_unverified')
        self.assertIsNone(r['controls'][1]['requirement_satisfied'])

    def test_all_present_still_not_approved(self):
        self.write_canonical([{'test_id': 'kdrs.c02', 'status': 'ok'},
                              {'test_id': 'noark5.xml-schema-validation.v1/arkivstruktur-xsd', 'status': 'ok'}])
        result = evaluate_control_profile(self.work, self.profile)
        self.assertEqual(result['summary']['required_without_registered_evidence'], [])
        self.assertIsNone(result['summary']['coverage_complete'])

    def test_rejects_claimed_approved_profile(self):
        data = json.loads(self.profile.read_text())
        self.write_profile(data['requirements'], approved=True)
        with self.assertRaisesRegex(ValueError, 'ikke-godkjent'):
            load_control_profile(self.profile)

    def test_rejects_duplicate_and_unknown_control(self):
        with self.assertRaisesRegex(ValueError, 'Duplisert'):
            self.write_profile([{'control_id': 'xpath', 'requirement': 'required'}] * 2)
            load_control_profile(self.profile)
        self.write_profile([{'control_id': 'unknown', 'requirement': 'required'}])
        with self.assertRaisesRegex(ValueError, 'ukjent'):
            load_control_profile(self.profile)

    def test_conditional_requires_explanation(self):
        self.write_profile([{'control_id': 'arkade_noark', 'requirement': 'conditional'}])
        with self.assertRaisesRegex(ValueError, 'Betinget'):
            load_control_profile(self.profile)

    def test_read_only(self):
        a, b = self.canonical.read_bytes(), self.profile.read_bytes()
        evaluate_control_profile(self.work, self.profile)
        self.assertEqual(a, self.canonical.read_bytes())
        self.assertEqual(b, self.profile.read_bytes())
        self.assertEqual(sorted(p.name for p in (self.work / 'noark5_evidence').iterdir()), ['canonical-results.json'])

    def test_bundled_draft_profile_is_valid(self):
        path = Path(__file__).resolve().parents[1] / 'config/noark5/control-profile-dwm-draft-v1.json'
        self.assertEqual(len(load_control_profile(path)['requirements']), 6)


if __name__ == '__main__':
    unittest.main()
