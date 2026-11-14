"""a5 regression: never promote a test reference to an evaluated metadata hit."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from noark5_workflow.analysis.canonical_context_v0115_a4 import build_context
from noark5_workflow.analysis.canonical_external_v0115_a5 import inspect_external


class A5ExternalAndLinkageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        (self.root / 'source').mkdir()
        uid = str(uuid4())
        (self.work / 'job.json').write_text(json.dumps({
            'file_type': 'dwm-work-job', 'format_version': 1, 'job_uid': uid,
            'job': {'job_id': 'JOB-001', 'source_extraction': str(self.root / 'source')},
        }), encoding='utf-8')
        self.evid = self.work / 'noark5_evidence'
        self.evid.mkdir()
        self.canonical = self.evid / 'canonical-results.json'
        self.canonical.write_text(json.dumps({
            'model_id': 'noark5.canonical-results.v1',
            'extraction': {'stable_id': uid},
            'observations': [{'test_id': 'kdrs.c02', 'metadata_id': None,
                              'source_kind': 'dwm_master'}],
        }), encoding='utf-8')
        self.assess = self.evid / 'experience_assessments.json'
        self.assess.write_text(json.dumps({
            'schema_version': '1.0', 'catalog_type': 'dwm_noark5_assessments',
            'events': [{'event_id': str(uuid4()), 'event_type': 'human_assessment',
                        'test_id': 'kdrs.c02', 'metadata_id': 'M300',
                        'decision': 'needs_follow_up', 'note': 'Not an M300 test'}],
        }), encoding='utf-8')
        self.external = self.work / 'external_evidence'
        self.external.mkdir()

    def test_m300_reference_is_not_verified(self):
        original = self.canonical.read_bytes()
        document = build_context(self.work, assessments_path=self.assess, write=False)
        assessment = document['assessments'][0]
        self.assertEqual(assessment['reference_status'], 'test_id_present')
        self.assertEqual(assessment['link_status'], 'test_id_only')
        self.assertEqual(assessment['evidence_verification'], 'not_verified')
        self.assertEqual(assessment['human_verification'], 'not_recorded')
        self.assertEqual(document['summary']['unverified_assessments'], 1)
        self.assertFalse(document['summary']['is_approval'])
        self.assertEqual(original, self.canonical.read_bytes())

    def test_unknown_arkade_is_not_converted_to_pass(self):
        path = self.external / 'arkade.json'
        path.write_text(json.dumps({'arkade': {'status': 'pass'}, 'tests': []}))
        context = build_context(self.work, external_paths=(path,), write=False)
        file = context['external_evidence'][0]
        self.assertEqual(file['interpretation'], 'not_parsed')
        self.assertEqual(file['source_kind'], 'external_opaque')
        self.assertEqual(context['summary']['identified_siegfried_files'], 0)

    def test_siegfried_json_inventory_only(self):
        path = self.external / 'sf.json'
        path.write_text(json.dumps({
            'siegfried': '1.11.0',
            'files': [{'filename': 'x.pdf', 'matches': [{'ns':'pronom','id':'fmt/18'}]},
                      {'filename': 'y.bin', 'matches': []}],
        }), encoding='utf-8')
        context = build_context(self.work, external_paths=(path,), write=False)
        ext = context['external_evidence'][0]
        self.assertEqual(ext['source_kind'], 'siegfried')
        self.assertEqual(ext['interpretation'], 'format_identification_only')
        self.assertEqual(ext['inspection']['file_records'], 2)
        self.assertEqual(ext['inspection']['identifiers'], [{'id': 'pronom:fmt/18', 'matches': 1}])
        self.assertIsNone(ext['inspection']['technical_test_status'])
        self.assertIsNone(ext['inspection']['approval'])
        self.assertEqual(context['summary']['identified_siegfried_files'], 1)

    def test_corrupt_siegfried_structure_stays_unparsed(self):
        path = self.external / 'sf.json'
        path.write_text(json.dumps({'siegfried': '1.11.0', 'files': [{'matches': {'id': 'fmt/18'}}]}))
        self.assertEqual(inspect_external(path)['interpretation'], 'not_parsed')

    def test_unrelated_json_no_false_siegfried(self):
        path = self.external / 'other.json'
        path.write_text(json.dumps({'files': [{'matches': []}]}))
        self.assertEqual(inspect_external(path)['format'], 'unrecognized')

    def test_readonly_dry_run(self):
        original = self.assess.read_bytes()
        build_context(self.work, assessments_path=self.assess, write=False)
        self.assertFalse((self.evid / 'canonical-context.json').exists())
        self.assertEqual(self.assess.read_bytes(), original)

    def test_unlinked_event_preserved(self):
        doc = json.loads(self.assess.read_text())
        doc['events'][0]['test_id'] = 'nonexistent.test'
        self.assess.write_text(json.dumps(doc))
        result = build_context(self.work, assessments_path=self.assess, write=False)
        self.assertEqual(result['assessments'][0]['reference_status'], 'no_matching_test_id')
        self.assertEqual(result['summary']['unlinked_assessments'], 1)

if __name__ == '__main__':
    unittest.main()

class A5DiscoveryTests(unittest.TestCase):
    def test_bounded_candidates_without_selection_or_parsing(self):
        from noark5_workflow.analysis.canonical_external_v0115_a5 import discover_external_candidates
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            ext = work / 'external_runs'
            ext.mkdir()
            for i in range(5):
                (ext / f'{i}.json').write_text('{}')
            (ext / 'irrelevant.exe').write_text('ignored')
            with patch('noark5_workflow.analysis.canonical_results._validate_work', return_value=(work, {'job_uid':'test'})):
                result = discover_external_candidates(work, limit=3)
            self.assertEqual(len(result), 3)
            self.assertEqual({x['status'] for x in result}, {'unselected'})
            self.assertEqual({x['interpretation'] for x in result}, {'not_inspected'})
