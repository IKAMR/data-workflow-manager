import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.xpath_test_engine import run_test

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'config' / 'noark5' / 'tests' / 'xpath_catalog_2026_05_26.json'


class A22U1DecompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
        cls.tests = {t['test_id']: t for t in cls.catalog['tests']}

    def test_catalog_is_a22_and_u_jobs_remain_regression_reference(self):
        self.assertGreaterEqual(self.catalog['catalog_format_version'], 7)
        self.assertTrue(self.catalog['status'].startswith('implementation_qa_a2'))
        self.assertIn('kdrs.u01', self.tests)
        self.assertIn('kdrs.u02', self.tests)

    def test_missing_u1_metrics_are_materialised_in_individual_tests(self):
        expected = {
            'kdrs.c02': {'archive_part_created_date_range', 'archive_part_closed_date_range'},
            'kdrs.c08': {'folder_created_date_range', 'folder_closed_date_range', 'case_date_range', 'meeting_date_range'},
            'kdrs.c14': {'archived_date_range'},
            'kdrs.c21': {'document_number_count', 'document_number_counts', 'document_type_counts'},
            'kdrs.c24': {'version_number_count', 'version_number_counts', 'format_count', 'format_counts', 'format_details_count', 'format_details_counts', 'file_size_stats', 'file_size_buckets'},
            'kdrs.f12': {'converted_from_format_count', 'converted_from_format_counts', 'converted_to_format_count', 'converted_to_format_counts', 'conversion_tool_count', 'conversion_tool_counts'},
        }
        for test_id, ids in expected.items():
            actual = {m['id'] for m in self.tests[test_id]['execution']['metrics']}
            self.assertTrue(ids <= actual, (test_id, ids - actual))

    def test_numeric_file_size_metrics(self):
        xml = '''<arkiv><dokumentobjekt><filstoerrelse>0</filstoerrelse></dokumentobjekt><dokumentobjekt><filstoerrelse>9</filstoerrelse></dokumentobjekt><dokumentobjekt><filstoerrelse>1000</filstoerrelse></dokumentobjekt><dokumentobjekt><filstoerrelse>100000000</filstoerrelse></dokumentobjekt></arkiv>'''
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'arkivstruktur.xml').write_text(xml, encoding='utf-8')
            result = run_test(self.tests['kdrs.c24'], root)
        self.assertEqual(result['status'], 'ok')
        stats = result['values']['file_size_stats']
        self.assertEqual(stats['count'], 4)
        self.assertEqual(stats['sum'], 100001009)
        self.assertEqual(stats['max'], 100000000)
        buckets = result['values']['file_size_buckets']
        self.assertEqual(buckets['eq_0'], 1)
        self.assertEqual(buckets['1_9'], 1)
        self.assertEqual(buckets['1000_1999'], 1)
        self.assertEqual(buckets['ge_100000000'], 1)

    def test_conversion_groups_are_generic(self):
        xml = '''<arkiv><dokumentobjekt><konvertering><konvertertFraFormat>A</konvertertFraFormat><konvertertTilFormat>B</konvertertTilFormat><konverteringsverktoey>Tool 1</konverteringsverktoey></konvertering></dokumentobjekt><dokumentobjekt><konvertering><konvertertFraFormat>A</konvertertFraFormat><konvertertTilFormat>C</konvertertTilFormat><konverteringsverktoey>Tool 2</konverteringsverktoey></konvertering></dokumentobjekt></arkiv>'''
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'arkivstruktur.xml').write_text(xml, encoding='utf-8')
            result = run_test(self.tests['kdrs.f12'], root)
        self.assertEqual(result['values']['converted_from_format_counts'], {'A': 2})
        self.assertEqual(result['values']['converted_to_format_counts'], {'B': 1, 'C': 1})
        self.assertEqual(result['values']['conversion_tool_counts'], {'Tool 1': 1, 'Tool 2': 1})


if __name__ == '__main__':
    unittest.main()
