"""Context a4 tests: bounded, source preserving, provenance truthful."""
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch

from noark5_workflow.analysis.canonical_context_v0115_a4 import build_context, ContextError

class A4ContextTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.uid = str(uuid4())
        (self.work / 'job.json').write_text(json.dumps({
            'file_type': 'dwm-work-job', 'format_version': 1, 'job_uid': self.uid,
            'job': {'job_id': 'JOB-001', 'source_extraction': str(self.source)}
        }), encoding='utf-8')
        self.evidence = self.work / 'noark5_evidence'
        self.evidence.mkdir()
        self.canonical = self.evidence / 'canonical-results.json'
        self.canonical.write_text(json.dumps({
            'model_id': 'noark5.canonical-results.v1',
            'extraction': {'stable_id': self.uid},
            'observations': [{'test_id': 'kdrs.c02', 'metadata_id': None}]
        }), encoding='utf-8')
        self.assess = self.evidence / 'experience_assessments.json'
        self.assess.write_text(json.dumps({
            'schema_version':'1.0','catalog_type':'dwm_noark5_assessments',
            'events':[{'event_type':'human_assessment','event_id':str(uuid4()),
                       'metadata_id':'M300','test_id':'kdrs.c02', 'decision':'needs_follow_up',
                       'note':'Example human assessment', 'observed_count':678}]
        }),encoding='utf-8')
        self.ext = self.work / 'external_evidence' / 'arkade.txt'
        self.ext.parent.mkdir()
        self.ext.write_text('not automatically parsed', encoding='utf-8')

    def test_links_and_preserves_canonical(self):
        before = self.canonical.read_bytes()
        output = build_context(self.work, assessments_path=self.assess,
                               external_paths=(self.ext,), generated_at='2026-11-14T00:00:00Z')
        self.assertEqual(output['summary']['human_assessments'],1)
        self.assertEqual(output['summary']['external_unparsed_files'],1)
        self.assertEqual(output['assessments'][0]['link_status'],'test_id_only')
        self.assertFalse(output['assessments'][0]['automatic_test_status_modified'])
        self.assertEqual(self.canonical.read_bytes(),before)
        self.assertEqual(json.loads((self.evidence/'canonical-context.json').read_text()), output)

    def test_dry_run_no_write(self):
        build_context(self.work, assessments_path=self.assess, write=False)
        self.assertFalse((self.evidence/'canonical-context.json').exists())

    def test_cross_work_rejected(self):
        outside = self.source / 'other.txt'
        outside.write_text('secret')
        with self.assertRaises(ContextError):
            build_context(self.work, external_paths=(outside,))

    def test_unsupported_assessments_rejected(self):
        self.assess.write_text('{}')
        with self.assertRaises(ContextError):
            build_context(self.work, assessments_path=self.assess)

    def test_duplicate_external_rejected(self):
        with self.assertRaises(ContextError):
            build_context(self.work, external_paths=(self.ext,self.ext))

    def test_requires_canonical_identity(self):
        doc=json.loads(self.canonical.read_text());doc['extraction']['stable_id']=str(uuid4())
        self.canonical.write_text(json.dumps(doc))
        with self.assertRaises(ContextError):
            build_context(self.work, assessments_path=self.assess)

    def test_no_selection_rejected(self):
        with self.assertRaises(ContextError):
            build_context(self.work)

if __name__ == '__main__':
    unittest.main()
