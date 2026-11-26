"""a15 evidence freshness must be proved from the exact Siegfried run."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from app.aftercare_v027_a15 import (
    reconcile_supplemental_audit, verify_siegfried_link,
)
from app.application_api import DwmApiError


class A15ProvenanceTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name) / 'work'
        self.evidence = self.work / 'noark5_evidence'
        self.evidence.mkdir(parents=True)
        self.run_id = '20261126T100000Z-12345678'
        self.external = self.work / 'external_evidence' / 'siegfried' / self.run_id
        self.external.mkdir(parents=True)
        manifest = self.external / 'manifest.json'
        statistics = self.external / 'pronom_statistics.json'
        self._write(manifest, {'run_id': self.run_id})
        self._write(statistics, {'run_id': self.run_id, 'files_total': 2})
        self.canonical = self.evidence / 'canonical-results.json'
        self._write(self.canonical, {
            'a7_evidence_sources': {'siegfried_pronom': {
                'manifest': manifest.relative_to(self.work).as_posix(),
                'manifest_sha256': sha256(manifest.read_bytes()).hexdigest(),
                'file': statistics.relative_to(self.work).as_posix(),
                'sha256': sha256(statistics.read_bytes()).hexdigest(),
            }}
        })

    @staticmethod
    def _write(path, data):
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    def test_new_run_verified_by_manifest_and_both_hashes(self):
        expected = verify_siegfried_link(self.work, self.run_id)
        self.assertEqual(expected['run_id'], self.run_id)
        self.assertTrue(expected['manifest'].endswith('/manifest.json'))

    def test_old_run_is_never_silently_selected(self):
        with self.assertRaises(DwmApiError):
            verify_siegfried_link(self.work, '20261125T010000Z-87654321')

    def test_tampered_source_is_rejected(self):
        manifest = self.external / 'manifest.json'
        self._write(manifest, {'run_id': self.run_id, 'tampered': True})
        with self.assertRaises(DwmApiError):
            verify_siegfried_link(self.work, self.run_id)

    def test_supplement_in_a230_is_classified_correctly(self):
        target = self.evidence / 'evidence-audit.json'
        self._write(target, {
            'not_configured_source_families': ['siegfried_pronom'],
            'missing_source_families': [],
            'verified_references': [{'kind': 'siegfried_pronom'}],
            'technical_approval': None,
        })
        def publish(root, relative, data):
            self._write(root / relative, data)
        with patch('noark5_workflow.operations.canonical_evidence_v022_a7._publish_json',
                   side_effect=publish):
            self.assertTrue(reconcile_supplemental_audit(self.work,
                            'siegfried_pronom_identification', self.run_id))
        audit = json.loads(target.read_text(encoding='utf-8'))
        self.assertEqual(audit['not_configured_source_families'], [])
        self.assertEqual(audit['supplemental_source_families'], ['siegfried_pronom'])
        self.assertIsNone(audit['technical_approval'])

    def test_no_supplemental_audit_without_verified_reference(self):
        self._write(self.evidence / 'evidence-audit.json', {
            'not_configured_source_families': ['siegfried_pronom'],
            'missing_source_families': [],
            'verified_references': [],
        })
        with self.assertRaises(DwmApiError):
            reconcile_supplemental_audit(self.work,
                                         'siegfried_pronom_identification', self.run_id)


if __name__ == '__main__':
    unittest.main()
