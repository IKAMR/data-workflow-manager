"""Regression tests for explicit canonical v1 projection (a1, carried into a2)."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from noark5_workflow.analysis.canonical_results import (
    CanonicalResultError, build_canonical_results, FILENAME, OUTPUT_SUBDIR,
)
from noark5_workflow.core.raw_result_store import RawResultStore


class CanonicalA1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.uid = str(uuid4())
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf8')
        (self.work / 'job.json').write_text(json.dumps({
            'file_type': 'dwm-work-job', 'format_version': 1, 'job_uid': self.uid,
            'job': {'job_id': 'JOB-001', 'source_extraction': str(self.source)},
        }), encoding='utf8')
        self.run = self.work / 'noark5_tests' / 'xpath' / 'RUN-001'
        (self.run / 'results').mkdir(parents=True)
        (self.run / 'master-results.json').write_text(json.dumps({
            'format_version': 1,
            'source': {'execution_profile': 'normal', 'catalog_id': 'noark5-tests'},
            'tests': [
                {'test_id': 'kdrs.c01', 'availability': 'available', 'role': 'master', 'result_file': 'results/a.json'},
                {'test_id': 'kdrs.c02', 'availability': 'unavailable', 'role': 'master_test_unavailable', 'result_file': 'results/b.json'},
            ],
        }), encoding='utf8')
        (self.run / 'results' / 'a.json').write_text(json.dumps({
            'test_id': 'kdrs.c01', 'status': 'ok', 'source_xml': 'arkivstruktur.xml',
            'values': {'mappe_count': 42, 'document_count': 7, 'optional': None, 'flag': True},
        }), encoding='utf8')
        (self.run / 'results' / 'b.json').write_text(json.dumps({
            'test_id': 'kdrs.c02', 'status': 'error', 'error': 'Noark XML missing',
        }), encoding='utf8')

    def build(self, **kw):
        return build_canonical_results(self.work, master_paths=(self.run / 'master-results.json',),
                                       recorded_at='2026-11-13T18:00:00+00:00', **kw)

    def test_materialize_master_with_evidence_and_unknowns(self):
        report = self.build()
        self.assertEqual(report['model_id'], 'noark5.canonical-results.v1')
        self.assertEqual(report['extraction']['stable_id'], self.uid)
        self.assertIsNone(report['extraction']['noark_version'])
        self.assertEqual(report['summary']['available_internal_master'], 1)
        self.assertEqual(report['summary']['observations'], 2)
        available, missing = report['observations']
        self.assertEqual(available['numeric_values'], {'mappe_count': 42, 'document_count': 7})
        self.assertFalse(available['metrics_aggregatable'])
        self.assertEqual(missing['availability'], 'unavailable')
        self.assertEqual(missing['numeric_values'], {})
        self.assertEqual(len(available['evidence'][0]['sha256']), 64)
        self.assertFalse('C:' in json.dumps(report))
        saved = json.loads((self.work / OUTPUT_SUBDIR / FILENAME).read_text(encoding='utf8'))
        self.assertEqual(saved, report)
        self.assertEqual((self.source / 'arkivstruktur.xml').read_text(encoding='utf8'), '<arkiv/>')

    def test_idempotent_observation_ids_without_overwriting_source(self):
        first = self.build()
        second = self.build()
        self.assertEqual([x['observation_id'] for x in first['observations']],
                         [x['observation_id'] for x in second['observations']])

    def test_dry_run_does_not_create_any_canonical_folder(self):
        self.build(write=False)
        self.assertFalse((self.work / OUTPUT_SUBDIR).exists())

    def test_reject_master_outside_work(self):
        with self.assertRaises(CanonicalResultError):
            build_canonical_results(self.work, master_paths=(self.source / 'arkivstruktur.xml',))
        self.assertFalse((self.work / OUTPUT_SUBDIR).exists())

    def test_reject_missing_or_invalid_job_identity(self):
        (self.work / 'job.json').unlink()
        with self.assertRaises(CanonicalResultError):
            self.build()

    def test_reject_overlap_of_work_and_source(self):
        p = self.work / 'job.json'
        job = json.loads(p.read_text(encoding='utf8'))
        job['job']['source_extraction'] = str(self.work)
        p.write_text(json.dumps(job), encoding='utf8')
        with self.assertRaises(CanonicalResultError):
            self.build()

    def test_reject_regression_master(self):
        p = self.run / 'master-results.json'
        data = json.loads(p.read_text(encoding='utf8'))
        data['source']['execution_profile'] = 'regression'
        p.write_text(json.dumps(data), encoding='utf8')
        with self.assertRaises(CanonicalResultError):
            self.build()

    def test_reject_conflicting_test_id_in_result(self):
        p = self.run / 'results' / 'a.json'
        data = json.loads(p.read_text(encoding='utf8'))
        data['test_id'] = 'other'
        p.write_text(json.dumps(data), encoding='utf8')
        with self.assertRaises(CanonicalResultError):
            self.build()

    def test_raw_and_external_are_separate_and_not_master(self):
        raw = self.work / 'wf' / 'results' / 'raw-results.jsonl'
        item = RawResultStore(raw).append(operation_id='op1', test_id='kdrs.c01',
                      definition_version='1', ok=True, message='OK', job_uid=self.uid)
        bank = self.work / 'external' / 'result-bank.json'
        bank.parent.mkdir()
        bank.write_text(json.dumps({
            'format_version': 2, 'resources': [
                {'resource_id': 'arkade5:import1:test1', 'source_system': 'Arkade 5', 'test_id': 'A1', 'status': 'failed', 'has_results': True},
                {'resource_id': 'kdrs_query:import1:1', 'source_system': 'KDRS Query', 'test_id': 'kdrs.c01', 'status': 'imported', 'has_results': True},
            ],
        }), encoding='utf8')
        report = self.build(raw_results_path=raw, external_bank_path=bank)
        self.assertEqual(len(report['observations']), 5)
        self.assertEqual(report['summary']['available_internal_master'], 1)
        self.assertEqual(report['summary']['external_observations'], 2)
        self.assertEqual([r['source_kind'] for r in report['observations']],
                         ['dwm_master', 'dwm_master', 'dwm_raw', 'arkade5', 'kdrs_query'])
        self.assertEqual(report['observations'][2]['evidence'][0]['result_id'], item.result_id)
        self.assertTrue(all(not x['metrics_aggregatable'] for x in report['observations']))

    def test_reject_raw_record_belonging_to_other_job(self):
        raw = self.work / 'wf' / 'results' / 'raw-results.jsonl'
        RawResultStore(raw).append(operation_id='op', test_id='test', definition_version='1',
                                   ok=True, message='OK', job_uid=str(uuid4()))
        with self.assertRaises(CanonicalResultError):
            self.build(raw_results_path=raw)

    def test_no_implicit_scan_or_empty_snapshot(self):
        with self.assertRaises(CanonicalResultError):
            build_canonical_results(self.work)

    def test_reject_master_result_referencing_other_run(self):
        outside = self.work / 'other.json'
        outside.write_text(json.dumps({'test_id': 'kdrs.c01', 'status': 'ok', 'values': {'n': 1}}), encoding='utf8')
        master = self.run / 'master-results.json'
        doc = json.loads(master.read_text(encoding='utf8'))
        doc['tests'][0]['result_file'] = '../../../other.json'
        master.write_text(json.dumps(doc), encoding='utf8')
        with self.assertRaises(CanonicalResultError):
            self.build()

    def test_prevent_symlink_output_redirect_out_of_work(self):
        redirect = self.work / OUTPUT_SUBDIR
        try:
            redirect.symlink_to(self.source, target_is_directory=True)
        except (NotImplementedError, OSError):
            self.skipTest('Symlinks unavailable on this platform')
        with self.assertRaises(CanonicalResultError):
            self.build()
        self.assertFalse((self.source / FILENAME).exists())

    def test_version_and_distribution(self):
        root = Path(__file__).resolve().parents[1]
        import tomllib
        from version import VERSION
        self.assertEqual(VERSION, '0.1.15-a2')
        with (root / 'pyproject.toml').open('rb') as handle:
            self.assertEqual(tomllib.load(handle)['project']['version'], '0.1.15a2')

    def test_schema_validates_materialized_snapshot_when_validator_available(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('jsonschema optional')
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / 'config/noark5/canonical_results_v1.schema.json').read_text(encoding='utf8'))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(self.build(write=False), schema)

    def test_model_schema_is_valid_json_and_has_core_entities(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / 'config/noark5/canonical_results_v1.schema.json').read_text(encoding='utf8'))
        self.assertEqual(schema['properties']['model_id']['const'], 'noark5.canonical-results.v1')
        self.assertIn('observations', schema['required'])
        self.assertIn('sources', schema['required'])


if __name__ == '__main__':
    unittest.main()
