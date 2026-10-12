from __future__ import annotations

import math
import unittest
from lxml import etree
from noark5_workflow.analysis import xpath_test_engine as engine
from noark5_workflow.analysis.xpath_fast_a154 import _fast_numeric_stats


class A1510NumericStatsTests(unittest.TestCase):
    def compare(self, xml, select):
        node = etree.fromstring(xml.encode('utf-8'))
        self.assertEqual(engine._numeric_stats(node, select),
                         _fast_numeric_stats(engine._numeric_stats, node, select))

    def test_empty(self):
        self.compare('<root/>', './/filstoerrelse')

    def test_normal(self):
        self.compare('<root><filstoerrelse>0</filstoerrelse><filstoerrelse>100</filstoerrelse><filstoerrelse>10.5</filstoerrelse></root>', './/filstoerrelse')

    def test_bad_and_negative(self):
        self.compare('<root><filstoerrelse>bad</filstoerrelse><filstoerrelse> </filstoerrelse><filstoerrelse>-3</filstoerrelse><filstoerrelse>5</filstoerrelse></root>', './/filstoerrelse')

    def test_archive_part(self):
        tree = etree.fromstring(b'<root><arkivdel><filstoerrelse>11</filstoerrelse></arkivdel><arkivdel><filstoerrelse>42</filstoerrelse></arkivdel></root>')
        for part in tree.findall('arkivdel'):
            self.assertEqual(engine._numeric_stats(part, './/filstoerrelse'), _fast_numeric_stats(engine._numeric_stats, part, './/filstoerrelse'))

    def test_complex_expression_uses_original(self):
        self.compare('<root><part><filstoerrelse>12</filstoerrelse></part><part><filstoerrelse>14</filstoerrelse></part></root>', './/part[1]/filstoerrelse')

    def test_monkeypatch_is_restored(self):
        from noark5_workflow.analysis import xpath_fast_a154
        old = engine._numeric_stats
        try:
            xpath_fast_a154.run_catalog_profiled('/nonexistent/a1510.json', '/nonexistent', '/nonexistent/out')
        except (FileNotFoundError, RuntimeError):
            pass
        self.assertIs(old, engine._numeric_stats)

if __name__ == '__main__':
    unittest.main()
