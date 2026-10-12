"""a15.8: date_range streaming matches the canonical XPath implementation."""
from __future__ import annotations

import unittest
from lxml import etree
from noark5_workflow.analysis import xpath_test_engine as engine
from noark5_workflow.analysis.xpath_fast_a154 import _fast_date_range


class A158DateRangeStreaming(unittest.TestCase):
    def _check(self, xml: str, selection: str, *, part: int | None = None):
        root = etree.fromstring(xml.encode("utf-8"))
        node = root if part is None else root.findall("part")[part]
        self.assertEqual(engine._date_range(node, selection),
                         _fast_date_range(engine._date_range, node, selection))

    def test_whole_extraction(self):
        self._check("<root><dt>2024-03-02</dt><dt>1999-01-01</dt>"
                    "<dt>2020-12-31</dt></root>", ".//dt")

    def test_archive_parts_isolated(self):
        xml = ("<root><part><dt>2024-01-01</dt><dt>2020-01-01</dt></part>"
               "<part><dt>1990-01-01</dt></part></root>")
        self._check(xml, ".//dt", part=0)
        self._check(xml, ".//dt", part=1)

    def test_nested_elements(self):
        self._check("<root><part><entry><date>2005-01-01</date></entry>"
                    "<entry><date>2002-01-01</date></entry></part></root>",
                    ".//entry/date")

    def test_empty_and_short(self):
        self._check("<root><dt/><dt>123</dt><dt>2021-01-01T12:00:00</dt></root>", ".//dt")

    def test_predicate_falls_back(self):
        self._check("<root><part><dt>2022-01-01</dt><dt>2010-12-31</dt></part>"
                    "<part><dt>2001-01-01</dt></part></root>", ".//part[1]/dt")

    def test_no_matches(self):
        self._check("<root><part/></root>", ".//dt")

    def test_unicode_and_whitespace(self):
        self._check("<root><dt> 2020-01-01 </dt><dt>  2000-12-31  </dt></root>", ".//dt")


if __name__ == "__main__":
    unittest.main()
