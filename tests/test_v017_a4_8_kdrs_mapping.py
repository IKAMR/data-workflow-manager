from __future__ import annotations
import unittest
from noark5_workflow.external_evidence.kdrs_query_mapping import map_resources


class TestKdrsMapping(unittest.TestCase):
    def test_lossless_standard_u1_u2_mapping(self):
        coverage = {'items': [{'id': 'folder_counts', 'legacy': ['U01', 'U02'],
                               'tests': ['kdrs.c08'], 'status': 'covered',
                               'scope': ['whole_extraction', 'archive_part']}]}
        catalog = {'tests': [{'test_id': 'kdrs.c08'}]}
        resources = []
        for index, (typ, test) in enumerate((('standard', 'kdrs.c08'), ('u01', 'legacy.u01'),
                                             ('u02', 'legacy.u02.archive_part.1'))):
            resources.append({'source_system': 'KDRS Query', 'resource_id': f'r{index}',
                              'report_type': typ, 'test_id': test,
                              'source_sha256': 'abc', 'archive_part_title': 'A' if typ == 'u02' else None,
                              'results': [{'text': 'Mapper: 8', 'values': [{'label': 'Mapper', 'value': 8}],
                                           'year_counts': {'2001': 2}}, {'text': 'unparsed', 'values': []}]})
        result = map_resources({'resources': resources}, coverage=coverage, catalog=catalog)
        self.assertEqual(result['summary']['resources'], 3)
        self.assertEqual(result['summary']['lines'], 6)
        self.assertEqual(result['summary']['numeric_observations'], 3)
        self.assertEqual(result['summary']['year_observations'], 3)
        self.assertEqual(result['resources'][0]['mapping_status'], 'catalog_test')
        self.assertEqual(result['resources'][1]['mapping_status'], 'coverage_candidates_only')
        self.assertEqual(result['resources'][2]['archive_part_title'], 'A')
        self.assertEqual(result['resources'][1]['lines'][0]['observations'][0]['metric_id'], None)
        self.assertEqual(result['resources'][2]['lines'][1]['raw_text'], 'unparsed')

if __name__ == '__main__':
    unittest.main()
