"""a16: regression error evidence must not crash or be silently accepted."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.legacy_regression import build_legacy_regression_comparison


CONTRACT = {
    'whole_extraction_comparisons': [
        {'id': 'folders', 'legacy_path': 'folders.count',
         'canonical_test': 'kdrs.c13', 'canonical_path': 'folder_count'},
    ],
    'archive_part_comparisons': [
        {'id': 'folders', 'legacy_path': 'folder_count',
         'canonical_test': 'kdrs.c13', 'canonical_path': 'folder_count'},
    ],
}


class RegressionUnavailableValuesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, test_id, data):
        (self.root / (test_id.replace('.', '_') + '.json')).write_text(
            json.dumps(data), encoding='utf-8')

    def test_a190_u02_error_is_reported_not_crashed_or_marked_match(self):
        self.write('kdrs.u01', {'status': 'error', 'error': 'MemoryError: source',})
        self.write('kdrs.u02', {'status': 'error', 'error': 'MemoryError: archive parts'})
        self.write('kdrs.c13', {'status': 'ok', 'values': {'folder_count': 3}})
        doc = build_legacy_regression_comparison(self.root, CONTRACT)
        self.assertEqual(doc['summary']['status'], 'review')
        self.assertEqual(doc['summary']['matches'], 0)
        self.assertTrue(doc['summary']['unavailable_archive_part_reference'])
        self.assertIn('kdrs.u02', doc['archive_part_reference']['error'])
        self.assertEqual(doc['whole_extraction']['folders']['status'], 'not_comparable')
        self.assertEqual(doc['archive_parts'], {})

    def test_missing_canonical_values_yields_not_comparable(self):
        self.write('kdrs.u01', {'status': 'ok', 'values': {'folders': {'count': 3}}})
        self.write('kdrs.u02', {'status': 'ok', 'values': {'archive_parts': []}})
        self.write('kdrs.c13', {'status': 'error', 'error': 'parse failed'})
        doc = build_legacy_regression_comparison(self.root, CONTRACT)
        self.assertEqual(doc['whole_extraction']['folders']['status'], 'not_comparable')
        self.assertIn('kdrs.c13', doc['whole_extraction']['folders']['error'])

    def test_missing_values_without_status_yields_explicit_diagnostic(self):
        self.write('kdrs.u01', {'values': {'folders': {'count': 3}}})
        self.write('kdrs.u02', {'status': 'ok'})
        self.write('kdrs.c13', {'values': {'folder_count': 3}})
        doc = build_legacy_regression_comparison(self.root, CONTRACT)
        self.assertEqual(doc['whole_extraction']['folders']['status'], 'match')
        self.assertEqual(doc['summary']['status'], 'review')
        self.assertIn('values mangler', doc['archive_part_reference']['error'])

    def test_valid_regression_keeps_existing_comparison_contract(self):
        self.write('kdrs.u01', {'values': {'folders': {'count': 3}}})
        self.write('kdrs.u02', {'values': {'archive_parts': [
            {'archive_part': {'system_id': 'A', 'index': 1},
             'values': {'folder_count': 3}},
        ]}})
        self.write('kdrs.c13', {'values': {'folder_count': 3, '_archive_parts': [
            {'archive_part': {'system_id': 'A'}, 'values': {'folder_count': 3}},
        ]}})
        doc = build_legacy_regression_comparison(self.root, CONTRACT)
        self.assertEqual(doc['summary']['matches'], 2)
        self.assertEqual(doc['summary']['checks'], 2)
        self.assertEqual(doc['summary']['status'], 'match')
        self.assertFalse(doc['summary']['unavailable_archive_part_reference'])


if __name__ == '__main__':
    unittest.main()
