"""a15.7: streaming year distributions, including per-archive-part scope."""
from __future__ import annotations

import unittest
from lxml import etree

from noark5_workflow.analysis import xpath_test_engine as engine
from noark5_workflow.analysis.xpath_fast_a154 import _fast_year_counts_text


class A157YearCountsTests(unittest.TestCase):
    def assert_equivalent(self, xml: str, select: str, *, per_part=False):
        root = etree.fromstring(xml.encode('utf-8'))
        nodes = list(root) if per_part else [root]
        for node in nodes:
            actual = _fast_year_counts_text(engine._year_counts, node, select)
            self.assertEqual(engine._year_counts(node, select), actual)

    def test_unsorted_and_repeated_dates(self):
        self.assert_equivalent('<root><dt>2023-01-01</dt><dt>2019-12-31</dt><dt>2023-02-03</dt></root>', './/dt')

    def test_short_values_are_preserved(self):
        self.assert_equivalent('<root><dt>1234</dt><dt>not valid</dt><dt>2</dt><dt> </dt><dt/></root>', './/dt')

    def test_nested_text_matches_legacy(self):
        self.assert_equivalent('<root><dt>202<b>4</b>-01-01</dt><dt>2033</dt></root>', './/dt')

    def test_each_archive_part_has_own_counts(self):
        self.assert_equivalent('<root><part><record><dt>2011-01-01</dt></record></part><part><record><dt>2024-01-01</dt></record></part></root>', './/record/dt', per_part=True)

    def test_complex_predicates_fallback(self):
        self.assert_equivalent('<root><part><dt>2023-01-01</dt></part><part><dt>2022-01-01</dt></part></root>', './/part[1]/dt')

    def test_absolute_selection_fallback(self):
        self.assert_equivalent('<root><dt>2023</dt><dt>2022</dt></root>', '//dt')

    def test_no_matching_elements(self):
        self.assert_equivalent('<root><dt>2023</dt></root>', './/other')

    def test_root_element_not_in_relative_descendants(self):
        self.assert_equivalent('<dt>2023-01-01<dt>2024-02-02</dt></dt>', './/dt')


if __name__ == '__main__':
    unittest.main()
