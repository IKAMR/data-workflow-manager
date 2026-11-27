"""Regression tests for reports generated after resuming a saved Work job."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from noark5_workflow.reporting.qa_decision_v021_a12 import (
    ReportInputError, _xpath_master_binding, build_snapshot, render_reports,
)


class A21ResumeReportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)
        self.job_id = 'JOB-002'
        self.uid = 'stable-job-identity'
        self.source = r'G:\archive\source'
        self.old = self.job_id + '__20261125T152421Z-first'
        self.new = self.job_id + '__20261127T185709Z-resume'
        self.master_rel = f'noark5_tests/xpath/{self.old}/master-results.json'
        self.report_rel = f'noark5_reports/depot_validation/{self.new}/depot_validation_report.json'
        self.master_manifest = self.master_rel.rsplit('/', 1)[0] + '/artifact_manifest.json'
        self.report_manifest = self.report_rel.rsplit('/', 1)[0] + '/artifact_manifest.json'
        self.job = {'file_type': 'dwm-work-job', 'format_version': 1, 'job_uid': self.uid,
                    'job': {'job_id': self.job_id, 'job_uid': self.uid,
                            'source_extraction': self.source}}
        self.put('job.json', self.job)
        self.put(self.master_rel, {'format_version': 1,
                                    'source': {'execution_profile': 'normal'},
                                    'tests': [{'test_id': 'C01', 'status': 'ok'}]})
        self.put(self.master_manifest, self.manifest(self.old, 'run_noark5_xpath_tests_2026'))
        self.put(self.report_manifest, self.manifest(self.new, 'build_noark5_depot_report'))
        self.depot = {'report_type': 'noark5_depot_validation',
                      'evidence': {'source_xpath_run': 'G:/archive/work/noark5_tests/xpath/' + self.old},
                      'summary': {'archive_part_count': 0}, 'archive_parts': [],
                      'technical_validation': {'status': 'ok', 'tests': [{'test_id': 'C01', 'status': 'ok'}]}}
        self.put(self.report_rel, self.depot)
        self.canonical = {'model_id': 'noark5.canonical-results.v1',
                          'extraction': {'stable_id': self.uid},
                          'sources': [{'source_kind': 'dwm_master',
                                       'reference': {'work_relative_path': self.master_rel,
                                                     'sha256': self.digest(self.master_rel)}}]}
        self.put('noark5_evidence/canonical-results.json', self.canonical)

    def put(self, relative, data):
        p = self.work / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False) + '\n', encoding='utf-8')
        return p

    def digest(self, relative):
        return sha256((self.work / relative).read_bytes()).hexdigest()

    def manifest(self, leaf, op):
        return {'schema_version': 2, 'run_id': leaf.split('__', 1)[1],
                'job_id': self.job_id, 'job_uid': self.uid,
                'source_extraction': self.source, 'operation_id': op}

    def binding(self, canonical=True):
        return _xpath_master_binding(self.work, self.work / self.report_rel,
                                     self.depot, self.job,
                                     canonical_masters=[self.master_rel] if canonical else None)

    def test_resumed_report_binds_original_master(self):
        snapshot = build_snapshot(work=self.work)
        binding = snapshot['xpath_source_binding']
        self.assertTrue(binding['cross_run'])
        self.assertEqual(binding['source_run'], self.old)
        self.assertEqual(binding['report_run'], self.new)
        self.assertEqual(binding['master_relative_path'], self.master_rel)
        self.assertEqual(len(binding['artifact_manifests']), 2)
        self.assertTrue(snapshot['review_required'])
        self.assertFalse(snapshot['depot_formal_decision_registered_by_a12'])

    def test_saved_work_resolves_original_master_without_canonical_index(self):
        binding = self.binding(canonical=False)
        self.assertEqual(binding['master_relative_path'], self.master_rel)
        self.assertTrue(binding['cross_run'])

    def test_master_content_change_is_rejected(self):
        self.put(self.master_rel, {'tampered': True})
        with self.assertRaisesRegex(ReportInputError, 'SHA-256'):
            build_snapshot(work=self.work)

    def test_foreign_job_in_manifest_is_rejected(self):
        for relative, leaf, operation in (
            (self.master_manifest, self.old, 'run_noark5_xpath_tests_2026'),
            (self.report_manifest, self.new, 'build_noark5_depot_report'),
        ):
            with self.subTest(relative=relative):
                data = self.manifest(leaf, operation)
                self.put(relative, {**data, 'job_uid': 'different-uid'})
                with self.assertRaisesRegex(ReportInputError, 'artefaktidentitet'):
                    self.binding()
                self.put(relative, data)

    def test_wrong_source_or_run_id_is_rejected(self):
        data = self.manifest(self.old, 'run_noark5_xpath_tests_2026')
        for key, value in [('source_extraction', r'G:\other'), ('run_id', 'wrong'),
                           ('operation_id', 'build_noark5_depot_report')]:
            with self.subTest(key=key):
                self.put(self.master_manifest, {**data, key: value})
                with self.assertRaisesRegex(ReportInputError, 'artefaktidentitet'):
                    self.binding()
        self.put(self.master_manifest, data)

    def test_wrong_canonical_run_or_foreign_job_is_rejected(self):
        for leaf in [self.old + '-other', 'JOB-999__different']:
            with self.subTest(leaf=leaf):
                self.depot['evidence']['source_xpath_run'] = 'noark5_tests/xpath/' + leaf
                with self.assertRaisesRegex(ReportInputError, 'XPath-kjøring'):
                    self.binding()

    def test_missing_or_unsafe_explicit_source_is_rejected(self):
        for value in ['', 'noark5_tests/xpath/../' + self.old, 'unrelated/' + self.old]:
            with self.subTest(value=value):
                self.depot['evidence']['source_xpath_run'] = value
                with self.assertRaises(ReportInputError):
                    self.binding()
        self.depot['evidence']['source_xpath_run'] = 'noark5_tests/xpath/' + self.old
        (self.work / self.master_manifest).unlink()
        with self.assertRaises(ReportInputError):
            self.binding()

    def test_legacy_same_run_keeps_existing_compatibility(self):
        path = self.work / f'noark5_reports/depot_validation/{self.old}/depot_validation_report.json'
        self.depot['evidence']['source_xpath_run'] = 'historic/' + self.old
        (self.work / self.master_manifest).unlink()
        result = _xpath_master_binding(self.work, path, self.depot, self.job,
                                       canonical_masters=[self.master_rel])
        self.assertFalse(result['cross_run'])
        self.assertEqual(result['artifact_manifests'], [])

    def test_a230_missing_noark_and_independent_pronom_are_visible(self):
        source_rel = 'external_evidence/arkade5_pronom/import/normalized/pronom_statistics.json'
        self.put(source_rel, {'evidence_type': 'arkade5_pronom_format_statistics'})
        digest = self.digest(source_rel)
        self.canonical['a7_evidence_sources'] = {'arkade_pronom': {'file': source_rel, 'sha256': digest}}
        self.put('noark5_evidence/canonical-results.json', self.canonical)
        canonical_hash = self.digest('noark5_evidence/canonical-results.json')
        self.put('noark5_evidence/evidence-audit.json', {
            'model_id': 'dwm.noark5.evidence-audit.a7.v1', 'job_uid': self.uid, 'job_id': self.job_id,
            'canonical_sha256': canonical_hash, 'missing_source_families': ['arkade_noark'],
            'status': 'missing_expected_sources'})
        self.put('noark5_evidence/canonical-external-analysis.json', {
            'extraction_stable_id': self.uid, 'canonical_reference': {'sha256': canonical_hash},
            'sources': [{'evidence': {'work_relative_path': source_rel, 'sha256': digest},
                         'analysis': {'source_format': 'arkade_pronom_statistics_v1',
                                      'interpretation': 'format_statistics_only',
                                      'reported_total_files': 748508, 'format_rows': 114}}]})
        snapshot = build_snapshot(work=self.work)
        coverage = snapshot['a21_evidence_coverage']
        self.assertEqual(coverage['missing_source_families'], ['arkade_noark'])
        self.assertFalse(coverage['automatic_approval'])
        self.assertEqual(coverage['pronom_sources'][0]['reported_format_occurrences'], 748508)
        self.assertEqual(snapshot['arkade']['status'], 'not_available')
        self.assertTrue(any(f['test_id'] == 'evidence.missing.arkade_noark' and f['severity'] == 'WARNING'
                            for f in snapshot['findings']))
        self.assertIn('748508', render_reports(snapshot)['01-kvalitetssikring-arkivskaper.html'])


if __name__ == '__main__':
    unittest.main()
