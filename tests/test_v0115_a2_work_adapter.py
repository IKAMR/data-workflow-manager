import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from noark5_workflow.analysis.canonical_work_adapter import (
    WorkAdapterError, canonical_report, discover_work_sources,
)


class WorkAdapterTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name) / 'work'
        self.work.mkdir()
        self.uid = str(uuid4())
        (self.work / 'job.json').write_text(json.dumps({
            'file_type': 'dwm-work-job', 'format_version': 1,
            'job_uid': self.uid, 'job': {'job_id': 'JOB-1'},
        }))

    def test_discover_normal_and_historical_separately(self):
        for name, profile in [('one', 'normal'), ('old', 'regression')]:
            p = self.work / 'noark5_tests' / name
            p.mkdir(parents=True)
            (p / 'master-results.json').write_text(json.dumps({
                'format_version': 1, 'source': {'execution_profile': profile}, 'tests': [],
            }))
        result = discover_work_sources(self.work)
        found = result['candidates']['master']
        self.assertEqual({x['status'] for x in found}, {'normal_master', 'unsupported_or_historical'})
        self.assertTrue(result['selection_required'])
        self.assertTrue(all(not x['selected'] for x in found))

    def test_raw_candidate_is_not_promoted_to_master(self):
        raw = self.work / 'wf' / 'results' / 'raw-results.jsonl'
        raw.parent.mkdir(parents=True)
        raw.write_text('{}\n')
        result = discover_work_sources(self.work)
        self.assertEqual(len(result['candidates']['raw']), 1)
        self.assertEqual(result['candidates']['master'], [])

    def test_no_job_is_rejected(self):
        (self.work / 'job.json').unlink()
        with self.assertRaises(WorkAdapterError):
            discover_work_sources(self.work)

    def test_coverage_does_not_sum_numbers_or_imply_approval(self):
        report = canonical_report({'model_id': 'noark5.canonical-results.v1',
            'extraction': {'stable_id': self.uid},
            'observations': [
                {'source_kind': 'dwm_master', 'availability': 'available', 'numeric_values': {'n': 42}},
                {'source_kind': 'dwm_master', 'availability': 'unavailable'},
                {'source_kind': 'arkade5', 'availability': 'unknown'},
            ]})
        self.assertEqual(report['observations'], 3)
        self.assertIsNone(report['technical_approval'])
        self.assertFalse(report['totals_aggregated'])
        self.assertEqual({r['source_kind']: r['observations'] for r in report['source_coverage']},
                         {'dwm_master': 2, 'arkade5': 1})

    def test_model_rejects_unknown(self):
        with self.assertRaises(WorkAdapterError):
            canonical_report({'model_id': 'different', 'observations': []})


if __name__ == '__main__':
    unittest.main()
