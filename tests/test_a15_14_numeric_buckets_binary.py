"""a15.14: bucket lookup retains original inclusive comparisons and scope."""
import unittest
from lxml import etree
from noark5_workflow.analysis import xpath_test_engine as engine
from noark5_workflow.analysis.xpath_fast_a154 import (
    _exclusive_bucket_index,
    _fast_numeric_buckets,
)


class A1514NumericBuckets(unittest.TestCase):
    def compare(self, values, buckets, select='.//n'):
        xml = '<root><part>' + ''.join('<n>' + str(v) + '</n>' for v in values) + '</part></root>'
        node = etree.fromstring(xml.encode())
        if select.startswith('.//') and '/part/' not in select:
            node = node[0]
        spec = {'select': select, 'buckets': buckets}
        self.assertEqual(
            engine._numeric_buckets(node, spec),
            _fast_numeric_buckets(engine._numeric_buckets, node, spec),
        )

    def test_disjoint_ordered_inclusive_intervals(self):
        buckets = [
            {'id': 'zero', 'min': 0, 'max': 0},
            {'id': 'one_nine', 'min': 1, 'max': 9},
            {'id': 'ten_99', 'min': 10, 'max': 99},
            {'id': 'large', 'min': 100, 'max': None},
        ]
        self.assertIsNotNone(_exclusive_bucket_index(buckets))
        self.compare(['-1','0','0.1','1','9','9.5','10','99','100','inf','nan','bad'], buckets)

    def test_gaps_are_not_accidentally_counted(self):
        buckets = [{'id':'a','min':1,'max':4},{'id':'b','min':10,'max':11}]
        self.compare(['0','1','4','4.5','9','10','11','12'], buckets)

    def test_overlapping_intervals_keep_multiple_matches(self):
        buckets = [{'id':'a','min':0,'max':10},{'id':'b','min':5,'max':20}]
        self.assertIsNone(_exclusive_bucket_index(buckets))
        self.compare(['4','5','10','11','21'], buckets)

    def test_unsorted_intervals_use_old_comparisons(self):
        buckets = [{'id':'b','min':11,'max':20},{'id':'a','min':0,'max':10}]
        self.assertIsNone(_exclusive_bucket_index(buckets))
        self.compare(['0','10','11','20','21'], buckets)

    def test_archive_part_relative_selection(self):
        buckets = [{'id':'tiny','min':0,'max':4},{'id':'big','min':5,'max':None}]
        self.compare(['0','4','5','100'], buckets, select='.//n')

    def test_index_rejects_overlapping_closed_bounds(self):
        self.assertIsNone(_exclusive_bucket_index([
            {'id':'a','min':0,'max':10},{'id':'b','min':10,'max':20},
        ]))


if __name__ == '__main__':
    unittest.main()
