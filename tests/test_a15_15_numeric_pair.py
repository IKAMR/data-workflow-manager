import unittest
from lxml import etree
from noark5_workflow.analysis import xpath_fast_a154 as fast
from noark5_workflow.analysis import xpath_test_engine as engine

BUCKETS = [{"id": "zero", "min": 0, "max": 0}, {"id": "small", "min": 1, "max": 9}, {"id": "large", "min": 10, "max": None}]
SPEC = {"id": "buckets", "type": "numeric_buckets", "select": ".//filstoerrelse", "buckets": BUCKETS}
STATS = {"id": "stats", "type": "numeric_stats", "select": ".//filstoerrelse"}

class A1515NumericPairTests(unittest.TestCase):
    def tearDown(self):
        fast._numeric_bucket_specs.clear()
        fast._numeric_pair_results.clear()

    def test_whole_and_parts_equivalent(self):
        tree = etree.ElementTree(etree.fromstring('<root><arkivdel><filstoerrelse>0</filstoerrelse><filstoerrelse>3</filstoerrelse><filstoerrelse>11</filstoerrelse></arkivdel><arkivdel><filstoerrelse>21</filstoerrelse><filstoerrelse>bad</filstoerrelse></arkivdel></root>'))
        fast._numeric_pair_specs({"execution": {"kind": "metrics", "metrics": [STATS, SPEC], "archive_part_metrics": [STATS, SPEC]}})
        for node in (tree, *tree.xpath('//arkivdel')):
            self.assertEqual(engine._numeric_stats(node, STATS['select']), fast._fast_numeric_stats_paired(engine._numeric_stats, node, STATS['select']))
            self.assertEqual(engine._numeric_buckets(node, SPEC), fast._fast_numeric_buckets_paired(engine._numeric_buckets, node, SPEC))
            self.assertFalse(fast._numeric_pair_results)

    def test_no_stats_no_pair(self):
        fast._numeric_pair_specs({"execution": {"kind": "metrics", "metrics": [SPEC]}})
        self.assertFalse(fast._numeric_bucket_specs)

    def test_conflict_disables_pair(self):
        conflict = dict(SPEC, buckets=[{"id": "other", "min": None, "max": None}])
        fast._numeric_pair_specs({"execution": {"kind": "metrics", "metrics": [STATS, SPEC], "archive_part_metrics": [STATS, conflict]}})
        self.assertFalse(fast._numeric_bucket_specs)

    def test_buckets_fallback_without_stats(self):
        tree = etree.ElementTree(etree.fromstring('<root><filstoerrelse>5</filstoerrelse></root>'))
        fast._numeric_pair_specs({"execution": {"kind": "metrics", "metrics": [STATS, SPEC]}})
        self.assertEqual(engine._numeric_buckets(tree, SPEC), fast._fast_numeric_buckets_paired(engine._numeric_buckets, tree, SPEC))

if __name__ == '__main__':
    unittest.main()
