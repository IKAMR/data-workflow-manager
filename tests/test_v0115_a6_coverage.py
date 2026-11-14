"""v0.1.15-a6 regression: coverage is evidence presence, never certification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from noark5_workflow.analysis.canonical_control_plan_v0115_a6 import coverage_report


class CoverageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name) / 'work'
        self.work.mkdir()
        self.uid = str(uuid4())
        self.folder = self.work / 'noark5_evidence'
        self.folder.mkdir()
        self.canonical = self.folder / 'canonical-results.json'
        self.write_canonical([{'test_id': 'kdrs.c02', 'status': 'ok', 'source_kind': 'dwm_master'},
                              {'test_id': 'arkade5_noark5_test', 'status': 'ok', 'source_kind': 'dwm_raw'}])
        self.validate_patch = patch('noark5_workflow.analysis.canonical_results._validate_work',
                                    return_value=(self.work, {'job_uid': self.uid}))
        self.validate_patch.start()
        self.addCleanup(self.validate_patch.stop)

    def write_canonical(self, observations):
        self.canonical.write_text(json.dumps({'model_id': 'noark5.canonical-results.v1',
                                               'extraction': {'stable_id': self.uid},
                                               'observations': observations}), encoding='utf-8')

    def test_registered_does_not_mean_passed_or_complete(self):
        report = coverage_report(self.work)
        self.assertEqual(report['summary']['categories_with_registered_evidence'], 2)
        self.assertFalse(report['summary']['mandatory_tests_verified'])
        self.assertIsNone(report['summary']['coverage_complete'])
        self.assertFalse(report['summary']['archive_approved'])
        arkade = next(x for x in report['controls'] if x['control_id'] == 'arkade_noark')
        self.assertEqual(arkade['presence'], 'registered')
        self.assertEqual(arkade['recorded_statuses'], {'ok': 1})
        self.assertEqual(arkade['compliance'], 'not_assessed')

    def test_missing_categories_are_not_zero_test_results(self):
        report = coverage_report(self.work)
        missing = next(x for x in report['controls'] if x['control_id'] == 'siegfried_pronom')
        self.assertEqual(missing['presence'], 'not_documented')
        self.assertEqual(missing['observation_count'], 0)
        self.assertEqual(missing['requirement'], 'profile_not_selected')

    def test_context_hash_match(self):
        sha = hashlib.sha256(self.canonical.read_bytes()).hexdigest()
        (self.folder / 'canonical-context.json').write_text(json.dumps({
            'model_id': 'noark5.canonical-context.v1',
            'canonical_reference': {'sha256': sha},
            'extraction_stable_id': self.uid,
        }), encoding='utf-8')
        self.assertEqual(coverage_report(self.work)['context_status'], 'linked')
        self.write_canonical([])
        self.assertEqual(coverage_report(self.work)['context_status'], 'stale_or_mismatched')

    def test_other_job_rejected(self):
        self.canonical.write_text(json.dumps({'model_id': 'noark5.canonical-results.v1',
                                               'extraction': {'stable_id': str(uuid4())},
                                               'observations': []}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'annen Work-jobb'):
            coverage_report(self.work)

    def test_no_write(self):
        original = self.canonical.read_bytes()
        coverage_report(self.work)
        self.assertEqual(self.canonical.read_bytes(), original)
        self.assertEqual(sorted(x.name for x in self.folder.iterdir()), ['canonical-results.json'])

    def test_malformed_canonical_fails_closed(self):
        self.canonical.write_text('{')
        with self.assertRaises(json.JSONDecodeError):
            coverage_report(self.work)


if __name__ == '__main__':
    unittest.main()
