"""a15.6: streamed min/max must preserve the original XPath date-range values."""
from __future__ import annotations

import unittest
from lxml import etree

from noark5_workflow.analysis import xpath_test_engine as engine
from noark5_workflow.analysis.xpath_fast_a154 import _fast_date_range


class A156DateRangeTests(unittest.TestCase):
    def assert_same(self, xml: str, select: str) -> None:
        node = etree.fromstring(xml.encode('utf-8'))
        self.assertEqual(engine._date_range(node, select), _fast_date_range(engine._date_range, node, select))

    def test_empty_and_short_values(self) -> None:
        self.assert_same('<root><dt/><dt> </dt><dt>2020</dt></root>', '//dt')

    def test_unsorted_and_duplicate_dates(self) -> None:
        self.assert_same('<root><dt>2024-12-01T14:00:00</dt><dt> 2020-01-03 </dt><dt>2024-12-01</dt><dt>2022-02-01</dt></root>', '//dt')

    def test_nested_text_and_unusual_values(self) -> None:
        self.assert_same('<root><dt>2023-<b>10</b>-11</dt><dt>not-a-date</dt><dt> 2021-05-17 </dt></root>', '//dt')

    def test_relative_archive_part_scope(self) -> None:
        self.assert_same('<root><part><dt>2022-01-01</dt><dt>2010-12-31</dt></part><part><dt>2001-01-01</dt></part></root>', './/part[1]/dt')

    def test_real_range_is_sorted_lexically_not_parsed(self) -> None:
        self.assert_same('<root><dt>2200-01-01</dt><dt>0500-01-01</dt><dt>2020-03-12</dt></root>', '//dt')


if __name__ == '__main__':
    unittest.main()
