import unittest
from noark5_workflow.external_evidence.number_format import format_count
import sys, types
try:
    from noark5_workflow.external_evidence import result_bank
except ImportError:
    stub = types.ModuleType("noark5_workflow.external_evidence.result_bank")
    stub.build_external_result_bank = lambda *args, **kwargs: {}
    sys.modules[stub.__name__] = stub
from noark5_workflow.external_evidence.kdrs_query_selection import METRICS

class A411Formatting(unittest.TestCase):
    def test_large_counts(self):
        self.assertEqual(format_count(64638), '64 638')
        self.assertEqual(format_count(66834), '66 834')
        self.assertEqual(format_count(1089071), '1 089 071')
        self.assertEqual(format_count(3436422), '3 436 422')
    def test_preserve_numeric_zeros(self):
        self.assertEqual(format_count(0), '0')
    def test_case_separate_from_folders(self):
        self.assertEqual(METRICS['case_count'], 'Saker')
        self.assertNotEqual(METRICS['case_count'], METRICS['folder_count'])
