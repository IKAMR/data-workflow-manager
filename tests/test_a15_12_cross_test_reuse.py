from __future__ import annotations

import unittest
from collections import OrderedDict
from lxml import etree
from noark5_workflow.analysis import xpath_test_engine as engine
from noark5_workflow.analysis.xpath_fast_a154 import _shared_eval_metrics, _shared_key


class A1512CrossTestReuse(unittest.TestCase):
    def setUp(self):
        self.first = etree.ElementTree(etree.fromstring(
            "<arkiv><arkivdel><mappe type='sak'/><mappe type='sak'/></arkivdel></arkiv>"))
        self.second = etree.ElementTree(etree.fromstring(
            "<arkiv><arkivdel><mappe type='sak'/><mappe type='sak'/></arkivdel></arkiv>"))

    def test_count_reused_across_individual_whole_tree_tests(self):
        cache = OrderedDict()
        calls = []
        def counted(node, metrics):
            calls.append(1)
            return engine._eval_metrics(node, metrics)
        first = [{"id": "folder_count", "type": "xpath", "expression": "count(//mappe)"}]
        second = [{"id": "folders_again", "type": "xpath", "expression": "count(//mappe)"}]
        self.assertEqual(_shared_eval_metrics(counted, cache, "arkivstruktur.xml", self.first, first)["folder_count"], 2)
        self.assertEqual(_shared_eval_metrics(counted, cache, "arkivstruktur.xml", self.second, second)["folders_again"], 2)
        self.assertEqual(len(calls), 1)

    def test_different_xml_file_does_not_reuse(self):
        cache, calls = OrderedDict(), []
        def counted(node, metrics):
            calls.append(1)
            return engine._eval_metrics(node, metrics)
        spec = [{"id":"n", "type":"xpath", "expression":"count(//mappe)"}]
        _shared_eval_metrics(counted, cache, "a.xml", self.first, spec)
        _shared_eval_metrics(counted, cache, "b.xml", self.second, spec)
        self.assertEqual(len(calls), 2)

    def test_archive_part_always_calculated(self):
        cache, calls = OrderedDict(), []
        def counted(node, metrics):
            calls.append(1)
            return engine._eval_metrics(node, metrics)
        spec = [{"id":"n", "type":"xpath", "expression":"count(.//mappe)"}]
        part = self.first.getroot()[0]
        _shared_eval_metrics(counted, cache, "a.xml", part, spec)
        _shared_eval_metrics(counted, cache, "a.xml", part, spec)
        self.assertEqual(len(calls), 2)
        self.assertFalse(cache)

    def test_cached_group_returns_defensive_copy(self):
        cache = OrderedDict()
        spec = [{"id":"by_type", "type":"group_attr", "select":"//mappe", "value":"@type"}]
        a = _shared_eval_metrics(engine._eval_metrics, cache, "a.xml", self.first, spec)
        a["by_type"]["sak"] = 99
        b = _shared_eval_metrics(engine._eval_metrics, cache, "a.xml", self.second, spec)
        self.assertEqual(b["by_type"]["sak"], 2)

    def test_complex_and_unbounded_metrics_not_cached(self):
        self.assertIsNone(_shared_key({"id":"x","type":"xpath","expression":"string(//mappe)"}))
        self.assertIsNone(_shared_key({"id":"x","type":"date_range","select":"//mappe[1]/dato"}))

if __name__ == "__main__":
    unittest.main()
