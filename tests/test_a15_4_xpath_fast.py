from __future__ import annotations

import unittest
from lxml import etree

from noark5_workflow.analysis import xpath_test_engine as engine
from noark5_workflow.analysis.xpath_fast_a154 import _fast_group, _fast_year_counts, run_catalog_profiled


class XPathFastA154Tests(unittest.TestCase):
    def setUp(self):
        self.root = etree.fromstring(b'''<arkiv><arkivdel>
            <mappe type="sak"/><mappe type="moete"/><mappe type="sak"/>
            <dokumentbeskrivelse><opprettetDato>2023-10-09</opprettetDato>
              <dokumentobjekt/><dokumentobjekt/></dokumentbeskrivelse>
            <dokumentbeskrivelse><opprettetDato>2024-01-05</opprettetDato>
              <dokumentobjekt/></dokumentbeskrivelse>
            <dokumentbeskrivelse><dokumentobjekt/></dokumentbeskrivelse>
        </arkivdel></arkiv>''')

    def test_group_attribute_matches_original(self):
        spec = {"id": "x", "type": "group_attr", "select": "//mappe", "value": "@type"}
        self.assertEqual(engine._group(self.root, spec), _fast_group(engine._group, self.root, spec))

    def test_parent_date_group_matches_original(self):
        spec = {"id": "x", "type": "group_xpath", "select": "//dokumentobjekt", "value": "string(ancestor::dokumentbeskrivelse[1]/opprettetDato)"}
        self.assertEqual(engine._group(self.root, spec), _fast_group(engine._group, self.root, spec))

    def test_parent_date_years_match_original(self):
        spec = {"id": "x", "type": "year_counts_by_node", "select": "//dokumentobjekt", "value": "string(ancestor::dokumentbeskrivelse[1]/opprettetDato)"}
        self.assertEqual(engine._year_counts_by_node(self.root, spec), _fast_year_counts(engine._year_counts_by_node, self.root, spec))

    def test_operation_uses_accelerated_runner(self):
        from noark5_workflow.operations import run_noark5_xpath_tests as operation
        self.assertIs(operation.run_catalog_profiled, run_catalog_profiled)

    def test_other_expressions_untouched(self):
        spec = {"id": "x", "type": "group_text", "select": "//opprettetDato"}
        self.assertEqual(engine._group(self.root, spec), _fast_group(engine._group, self.root, spec))


if __name__ == "__main__":
    unittest.main()
