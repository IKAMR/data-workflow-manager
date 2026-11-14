"""Regression fixtures for DWM-normalized Arkade 5 and PRONOM JSON.

Synthetic fixtures: never commit actual depot evidence to the repository.
"""
import importlib.util
import json
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'noark5_workflow/analysis/canonical_external_import_v0115_a10.py'
spec = importlib.util.spec_from_file_location('a10_fix_adapter', MODULE)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class RealArkadeShapeTests(unittest.TestCase):
    def test_dwm_normalized_arkade_v2(self):
        doc = {
            'format_version': 2, 'evidence_type': 'external_validation_report',
            'source_system': 'Arkade 5', 'source_version': '2.13.1',
            'summary': {'number_of_tests_run': '2 av 2', 'number_of_errors': '1'},
            'tests': [
                {'test_id': 'N5.01', 'test_name': 'Existence', 'test_type': 'StructureControl',
                 'source_status': 'ok', 'number_of_errors': 0, 'results': []},
                {'test_id': 'N5.22', 'test_name': 'Journal status', 'test_type': 'ContentAnalysis',
                 'source_status': 'error', 'number_of_errors': 1,
                 'results': [{'result_type': 'Error', 'message': 'Journalstatus: Journalført - Antall: 20',
                              'result_set_path': ['Arkivdel: el 4'], 'location': {'string': ''}}]},
            ]}
        got = adapter._arkade_entries(doc, 'external_evidence/arkade5/run/normalized/arkade5_results.json')
        self.assertEqual(got['source_format'], 'arkade_normalized_v2')
        self.assertEqual(got['record_count'], 2)
        self.assertEqual(got['reported_status_counts'], {'error': 1, 'ok': 1})
        self.assertEqual(got['records'][1]['reported_issues'][0]['result_set_path'], ['Arkivdel: el 4'])
        self.assertEqual(got['records'][1]['reported_status'], 'error')
        self.assertEqual(got['records'][1]['technical_verification'], 'not_verified')
        self.assertIsNone(got['records'][1]['depot_approval'])

    def test_pronom_statistics_v1(self):
        doc = {'format_version': 1, 'evidence_type': 'arkade5_pronom_format_statistics',
               'source_system': 'Arkade 5', 'csv': {'rows': [
                   {'Format-ID': 'fmt/354', 'Filtype': 'PDF/A', 'Formatversjon': '1b',
                    'RAF-220301': 'Gyldig', 'Antall': '635'},
                   {'Format-ID': 'fmt/17', 'Filtype': 'PDF', 'Formatversjon': '1.3',
                    'RAF-220301': 'Ikke gyldig', 'Antall': '2'}]}}
        got = adapter._pronom_statistics(doc, 'external_evidence/arkade5/run/normalized/pronom_statistics.json')
        self.assertEqual(got['reported_total_files'], 637)
        self.assertEqual(got['formats'][1]['reported_raf_220301'], 'Ikke gyldig')
        self.assertEqual(got['interpretation'], 'format_statistics_only')
        self.assertIsNone(got['depot_approval'])

    def test_never_assume_status_for_unsupported_schema(self):
        got = adapter._arkade_entries({'tests': [{'test_id': 'N5.22', 'source_status': 'error'}]},
                                      'external_evidence/arkade5/run/normalized/arkade5_results.json')
        self.assertEqual(got['interpretation'], 'not_parsed')


if __name__ == '__main__':
    unittest.main()
