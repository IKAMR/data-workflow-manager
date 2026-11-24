"""Regression: A160 can attach PRONOM to a different Arkade manifest than A210.

All files are synthetic and isolated inside TemporaryDirectory. The checks
exercise the genuine v0.2.5 legacy selection/audit plus v0.2.6-a3 recovery;
no real Source, Work, Arkade CLI or Qt is opened.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch
from uuid import uuid4

from noark5_workflow.operations import canonical_evidence_v022_a7 as old
from noark5_workflow.operations import canonical_evidence_v026_a3 as revised


def store(path: Path, doc: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False) + '\n', encoding='utf-8')


def digest(path: Path):
    return sha256(path.read_bytes()).hexdigest()


class A230SourceRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name) / 'work'
        self.work.mkdir()
        self.job_id = 'JOB-003'
        self.uid = str(uuid4())
        self.source = str(Path(temp.name) / 'source')
        store(self.work / 'job.json', {
            'file_type': 'dwm-work-job', 'format_version': 1,
            'job_uid': self.uid,
            'job': {
                'job_id': self.job_id, 'source_extraction': self.source,
                'workflow_ids': [
                    'run_noark5_xpath_tests_2026',
                    'arkade5_noark5_test',
                    'arkade5_pronom_analysis',
                    'siegfried_pronom_identification',
                ],
            },
        })
        master = self.work / 'noark5_tests/xpath/run1'
        store(master / 'master-results.json', {
            'format_version': 1,
            'source': {'execution_profile': 'normal'},
            'tests': [{'test_id': 'synthetic-test'}],
        })
        store(master / 'artifact_manifest.json', {
            'operation_id': 'run_noark5_xpath_tests_2026',
            'job_id': self.job_id, 'job_uid': self.uid,
            'source_extraction': self.source, 'run_id': 'RUN001',
        })
        self.old_import = self._arkade('old', '2026-11-21T09:00:00Z', pronom=True)
        self.new_import = self._arkade('new', '2026-11-22T09:00:00Z', pronom=False)
        siegfried = self.work / 'external_evidence/siegfried/run1'
        store(siegfried / 'pronom_statistics.json', {'files_total': 1})
        store(siegfried / 'manifest.json', {
            'job_id': self.job_id, 'job_uid': self.uid,
            'source_root': self.source, 'created_at': '2026-11-22T09:00:00Z',
        })
        self.identity = {'job_id': self.job_id, 'job_uid': self.uid}
        canonical = ModuleType('noark5_workflow.analysis.canonical_results')
        canonical._validate_work = lambda _root: (self.work, self.identity)
        canonical.build_canonical_results = lambda _root, *, master_paths, write: {
            'model_id': 'noark5.canonical-results.v1',
            'extraction': {'stable_id': self.uid},
            'observations': [{'test_id': 'synthetic-test'}],
            'limitations': [],
        }
        external = ModuleType('noark5_workflow.analysis.canonical_external_import_v0115_a10')
        external.MAX_SOURCE_NORMALIZED = 48 * 1024 * 1024
        external.MAX_ANALYSIS_OUTPUT = 128 * 1024 * 1024

        def analyze(root, selected_files=(), write=False):
            self.assertFalse(write)
            self.assertEqual(root, self.work)
            return {
                'model_id': 'noark5.external-analysis.v1',
                'extraction_stable_id': self.uid,
                'canonical_reference': {'sha256': digest(self.work / 'noark5_evidence/canonical-results.json')},
                'sources': [
                    {'evidence': {'work_relative_path': p, 'sha256': digest(root / p)},
                     'analysis': {'interpretation': 'format_statistics_only'}}
                    for p in selected_files
                ],
                'summary': {'unparsed_files': 0},
            }

        external.analyze_external_results = analyze
        modules = {
            'noark5_workflow.analysis.canonical_results': canonical,
            'noark5_workflow.analysis.canonical_external_import_v0115_a10': external,
        }
        patcher = patch.dict(sys.modules, modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.external = external

    def _arkade(self, import_id, timestamp, *, pronom):
        base = self.work / 'external_evidence' / 'arkade5' / import_id
        original = base / 'source' / 'noark-report.json'
        store(original, {'kind': 'original noark', 'id': import_id})
        normalized = base / 'normalized' / 'arkade5_results.json'
        store(normalized, {'source_system': 'Arkade 5',
                           'tests': [{'test_id': 'N5.01'}]})
        source_rel = original.relative_to(self.work).as_posix()
        manifest = {
            'import_id': import_id, 'imported_at': timestamp,
            'imported_by': {'job_id': self.job_id},
            'source': {'preserved_file': source_rel, 'sha256': digest(original)},
            'normalized_file': normalized.relative_to(self.work).as_posix(),
        }
        if pronom:
            csv = base / 'source' / 'filformatinfo-statistikk.csv'
            csv.parent.mkdir(parents=True, exist_ok=True)
            csv.write_text('Format-ID;Antall\nfmt/18;1\n', encoding='utf-8')
            stat = base / 'normalized' / 'pronom_statistics.json'
            store(stat, {
                'format_version': 1, 'source_system': 'Arkade 5',
                'evidence_type': 'arkade5_pronom_format_statistics',
                'source': {'preserved_file': csv.relative_to(self.work).as_posix(),
                           'sha256': digest(csv)},
                'csv': {'rows': [{'Format-ID': 'fmt/18', 'Antall': '1'}]},
            })
            manifest['pronom_evidence'] = {'statistics': {
                'found': True, 'imported': True,
                'normalized_file': stat.relative_to(self.work).as_posix(),
                'sha256': digest(csv),
            }}
        store(base / 'manifest.json', manifest)
        return base

    def _legacy_a230_failure(self):
        # Emulate the actual affected job: A210 + A220 were already completed
        # before the PRONOM manifest-selection defect is fixed.
        built = old.build_evidence(self.work, job_id=self.job_id)
        self.assertEqual(set(built['external_sources']), {'arkade_noark', 'siegfried_pronom'})
        old.analyze_external(self.work, job_id=self.job_id)
        report = old.audit_evidence(self.work, job_id=self.job_id)
        self.assertEqual(report['missing'], ['arkade_pronom'])

    def test_a210_links_verified_pronom_from_older_import(self):
        report = revised.build_evidence(self.work, job_id=self.job_id)
        self.assertEqual(set(report['external_sources']),
                         {'arkade_noark', 'arkade_pronom', 'siegfried_pronom'})
        canonical = json.loads((self.work/'noark5_evidence/canonical-results.json').read_text())
        sources = canonical['a7_evidence_sources']
        self.assertIn('/new/normalized/arkade5_results.json', sources['arkade_noark']['file'])
        self.assertIn('/old/normalized/pronom_statistics.json', sources['arkade_pronom']['file'])

    def test_a230_recovers_existing_failed_job_without_cli_rerun(self):
        self._legacy_a230_failure()
        canonical = self.work / 'noark5_evidence/canonical-results.json'
        analysis = self.work / 'noark5_evidence/canonical-external-analysis.json'
        old_a210 = canonical.read_bytes()
        old_a220 = analysis.read_bytes()
        recovered = revised.audit_evidence(self.work, job_id=self.job_id)
        self.assertEqual(recovered['missing'], [])
        self.assertEqual(recovered['linked'], 3)
        self.assertEqual(recovered['recovered'], ['arkade_pronom'])
        audit = json.loads((self.work/'noark5_evidence/evidence-audit.json').read_text())
        self.assertEqual(audit['a230_relinked']['family'], 'arkade_pronom')
        self.assertFalse(audit['a230_relinked']['automatic_approval'])
        self.assertEqual(audit['status'], 'sources_linked_needs_review')
        hist = self.work / 'noark5_evidence/history'
        self.assertTrue((hist / ('canonical-results-' + sha256(old_a210).hexdigest() + '.json')).is_file())
        self.assertTrue((hist / ('canonical-external-analysis-' + sha256(old_a220).hexdigest() + '.json')).is_file())
        # A230 does not modify the authoritative job, its cursor, or the CSV.
        self.assertEqual(json.loads((self.work/'job.json').read_text())['job']['job_id'], self.job_id)
        self.assertEqual((self.old_import/'source/filformatinfo-statistikk.csv').read_text(),
                         'Format-ID;Antall\nfmt/18;1\n')

    def test_a230_missing_csv_remains_failure_with_precise_reason(self):
        self._legacy_a230_failure()
        (self.old_import/'source/filformatinfo-statistikk.csv').unlink()
        result = revised.audit_evidence(self.work, job_id=self.job_id)
        self.assertEqual(result['missing'], ['arkade_pronom'])
        self.assertIn('PRONOM', result['missing_reasons']['arkade_pronom'])
        audit = json.loads((self.work/'noark5_evidence/evidence-audit.json').read_text())
        self.assertIn('missing_source_reasons', audit)

    def test_tampered_csv_is_not_accepted_as_recovered_source(self):
        self._legacy_a230_failure()
        (self.old_import/'source/filformatinfo-statistikk.csv').write_text(
            'Format-ID;Antall\nfmt/18;999\n', encoding='utf-8')
        result = revised.audit_evidence(self.work, job_id=self.job_id)
        self.assertEqual(result['missing'], ['arkade_pronom'])
        self.assertFalse(result.get('recovered'))
        self.assertIn('SHA-256', result['missing_reasons']['arkade_pronom'])

    def test_ambiguous_old_pronom_imports_require_explicit_choice(self):
        self._legacy_a230_failure()
        # A second, independently verified older PRONOM has the same
        # import timestamp. A230 must not silently choose one by filename.
        self._arkade('second-old', '2026-11-21T09:00:00Z', pronom=True)
        result = revised.audit_evidence(self.work, job_id=self.job_id)
        self.assertEqual(result['missing'], ['arkade_pronom'])
        self.assertIn('entydig', result['missing_reasons']['arkade_pronom'])

    def test_other_missing_family_prevents_partial_repair(self):
        self._legacy_a230_failure()
        # Remove the stored Siegfried source but keep its operation selected,
        # as in a partially imported Work.
        (self.work/'external_evidence/siegfried/run1/manifest.json').unlink()
        old.build_evidence(self.work, job_id=self.job_id)
        old.analyze_external(self.work, job_id=self.job_id)
        result = revised.audit_evidence(self.work, job_id=self.job_id)
        self.assertEqual(set(result['missing']), {'arkade_pronom', 'siegfried_pronom'})
        self.assertFalse(result.get('recovered'))

    def test_foreign_or_unowned_import_cannot_be_claimed(self):
        self._legacy_a230_failure()
        manifest = self.old_import / 'manifest.json'
        doc = json.loads(manifest.read_text())
        doc['imported_by']['job_id'] = 'JOB-999'
        store(manifest, doc)
        result = revised.audit_evidence(self.work, job_id=self.job_id)
        self.assertEqual(result['missing'], ['arkade_pronom'])
        self.assertFalse(result.get('recovered'))

    def test_rolls_back_derivative_files_when_a220_refresh_fails(self):
        self._legacy_a230_failure()
        original_a210 = (self.work/'noark5_evidence/canonical-results.json').read_bytes()
        original_a220 = (self.work/'noark5_evidence/canonical-external-analysis.json').read_bytes()
        with patch.object(self.external, 'analyze_external_results', side_effect=ValueError('analyzer failed')):
            with self.assertRaisesRegex(old.EvidenceError, 'gjenopprettet'):
                revised.audit_evidence(self.work, job_id=self.job_id)
        self.assertEqual((self.work/'noark5_evidence/canonical-results.json').read_bytes(), original_a210)
        self.assertEqual((self.work/'noark5_evidence/canonical-external-analysis.json').read_bytes(), original_a220)

    def test_rolls_back_audit_if_recovery_metadata_cannot_be_saved(self):
        self._legacy_a230_failure()
        canonical = self.work/'noark5_evidence/canonical-results.json'
        external = self.work/'noark5_evidence/canonical-external-analysis.json'
        audit_path = self.work/'noark5_evidence/evidence-audit.json'
        originals = [f.read_bytes() for f in (canonical, external)]
        writer = old._publish_json

        def fail_on_recovery_note(root, relative, document):
            if relative.endswith('/evidence-audit.json') and document.get('a230_relinked'):
                raise OSError('synthetic publish error')
            return writer(root, relative, document)

        with patch.object(old, '_publish_json', side_effect=fail_on_recovery_note):
            with self.assertRaisesRegex(old.EvidenceError, 'gjenopprettet'):
                revised.audit_evidence(self.work, job_id=self.job_id)
        self.assertEqual([f.read_bytes() for f in (canonical, external)], originals)
        audit = json.loads(audit_path.read_text())
        self.assertEqual(audit['missing_source_families'], ['arkade_pronom'])
        self.assertEqual(audit['status'], 'missing_expected_sources')

    def test_a230_operation_result_stays_red_when_expected_source_missing(self):
        from noark5_workflow.core.context import OperationContext
        self._legacy_a230_failure()
        (self.old_import/'source/filformatinfo-statistikk.csv').unlink()
        ctx = OperationContext(extraction_root=self.work,
                               work_operations=self.work,
                               metadata={'job_id': self.job_id})
        result = revised.AuditNoark5EvidenceOperation().run(ctx)
        self.assertFalse(result.ok)
        self.assertIn('arkade_pronom', result.message)
        self.assertIn('Årsak:', result.message)


class V026A3WiringTests(unittest.TestCase):
    def test_profile_uses_v026_a3_a210_and_a230(self):
        from noark5_workflow.profile import NOARK5_PROFILE
        factories = {f.definition.operation_id: f for f in NOARK5_PROFILE.operation_factories}
        self.assertIs(factories['build_noark5_canonical_evidence'],
                      revised.BuildNoark5CanonicalEvidenceOperation)
        self.assertIs(factories['audit_noark5_evidence'],
                      revised.AuditNoark5EvidenceOperation)
        self.assertEqual(factories['analyze_noark5_external_evidence'].__module__,
                         'noark5_workflow.operations.canonical_evidence_v022_a7')


if __name__ == '__main__':
    unittest.main()
