"""a15.13: reuse identical bounded whole-extraction summaries safely."""
from __future__ import annotations

import unittest
from collections import OrderedDict
from lxml import etree

from noark5_workflow.analysis import xpath_test_engine as engine
from noark5_workflow.analysis.xpath_fast_a154 import _shared_eval_metrics, _shared_key


class A1513SharedSummaries(unittest.TestCase):
    def setUp(self):
        xml = ("<arkiv><arkivdel><mappe><opprettetDato>2022-01-05</opprettetDato>"
               "<filstoerrelse>10</filstoerrelse></mappe>"
               "<mappe><opprettetDato>2020-02-01</opprettetDato>"
               "<filstoerrelse>20</filstoerrelse></mappe></arkivdel></arkiv>")
        self.tree = etree.ElementTree(etree.fromstring(xml))
        self.other_tree = etree.ElementTree(etree.fromstring(xml))

    def test_summary_results_match_original_and_are_reused(self):
        for kind, path in [
            ("date_range", "//mappe/opprettetDato"),
            ("year_counts", "//mappe/opprettetDato"),
            ("numeric_stats", "//filstoerrelse"),
        ]:
            with self.subTest(kind=kind):
                cache = OrderedDict()
                calls = []
                def counted(node, metrics):
                    calls.append(1)
                    return engine._eval_metrics(node, metrics)
                first = {"id": "first", "type": kind, "select": path}
                second = {"id": "second", "type": kind, "select": path}
                original = engine._eval_metrics(self.tree, [first])["first"]
                result_a = _shared_eval_metrics(counted, cache, "a.xml", self.tree, [first])
                result_b = _shared_eval_metrics(counted, cache, "a.xml", self.other_tree, [second])
                self.assertEqual(result_a["first"], original)
                self.assertEqual(result_b["second"], original)
                self.assertEqual(len(calls), 1)
                result_a["first"]["changed"] = "not cached"
                self.assertNotIn("changed", result_b["second"])

    def test_not_reused_between_different_sources_or_parts(self):
        calls = []
        def counted(node, metrics):
            calls.append(1)
            return engine._eval_metrics(node, metrics)
        spec = [{"id": "dates", "type": "date_range", "select": ".//opprettetDato"}]
        cache = OrderedDict()
        _shared_eval_metrics(counted, cache, "a.xml", self.tree, spec)
        _shared_eval_metrics(counted, cache, "b.xml", self.other_tree, spec)
        self.assertEqual(len(calls), 2)
        part = self.tree.getroot()[0]
        _shared_eval_metrics(counted, cache, "a.xml", part, spec)
        self.assertEqual(len(calls), 3)

    def test_complex_paths_and_unbounded_results_not_cached(self):
        for kind, path in [
            ("date_range", "//mappe[1]/opprettetDato"),
            ("year_counts", ".//mappe[@type='sak']/opprettetDato"),
            ("numeric_stats", "(//filstoerrelse)[1]"),
        ]:
            self.assertIsNone(_shared_key({"id": "m", "type": kind, "select": path}))
        self.assertIsNone(_shared_key({"id": "m", "type": "rows", "select": "//mappe"}))

    def test_missing_source_disables_shared_cache(self):
        cache = OrderedDict()
        spec = [{"id": "n", "type": "date_range", "select": "//mappe/opprettetDato"}]
        _shared_eval_metrics(engine._eval_metrics, cache, "", self.tree, spec)
        self.assertFalse(cache)


if __name__ == "__main__":
    unittest.main()
