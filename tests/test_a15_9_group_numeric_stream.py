from __future__ import annotations

import unittest
from lxml import etree

from noark5_workflow.analysis import xpath_test_engine as engine
from noark5_workflow.analysis.xpath_fast_a154 import (
    _fast_group, _fast_numeric_buckets, _fast_year_counts,
)


class A159StreamingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = etree.fromstring(b'''<arkiv>
          <arkivdel><mappe type="saksmappe"><saksstatus> A </saksstatus>
            <dokumentbeskrivelse><opprettetDato>2018-02-03</opprettetDato>
              <dokumentobjekt><filstoerrelse>0</filstoerrelse><variantformat>A</variantformat></dokumentobjekt>
              <dokumentobjekt><filstoerrelse>9</filstoerrelse><variantformat>B</variantformat></dokumentobjekt>
            </dokumentbeskrivelse></mappe></arkivdel>
          <arkivdel><mappe type="moetemappe"><saksstatus>B</saksstatus>
            <dokumentbeskrivelse><opprettetDato>2021-01-01</opprettetDato>
              <dokumentobjekt><filstoerrelse>10</filstoerrelse><variantformat>A</variantformat></dokumentobjekt>
              <dokumentobjekt><filstoerrelse>bad</filstoerrelse></dokumentobjekt>
            </dokumentbeskrivelse></mappe></arkivdel>
        </arkiv>''')

    def test_group_text_per_part(self):
        spec = dict(id='status', type='group_text', select='.//mappe/saksstatus')
        for node in [self.tree, *self.tree.findall('arkivdel')]:
            self.assertEqual(engine._group(node, spec), _fast_group(engine._group, node, spec))

    def test_group_attr_per_part(self):
        spec = dict(id='type', type='group_attr', select='.//mappe', value='@type')
        for node in [self.tree, *self.tree.findall('arkivdel')]:
            self.assertEqual(engine._group(node, spec), _fast_group(engine._group, node, spec))

    def test_group_text_complex_fallback(self):
        spec = dict(id='status', type='group_text', select='.//mappe[1]/saksstatus')
        self.assertEqual(engine._group(self.tree, spec), _fast_group(engine._group, self.tree, spec))

    def test_numeric_buckets_per_part(self):
        spec = dict(id='b', type='numeric_buckets', select='.//filstoerrelse', buckets=[
            dict(id='zero', min=0, max=0), dict(id='tiny', min=0, max=9),
            dict(id='small', min=9, max=10), dict(id='all', min=None, max=None),
        ])
        for node in [self.tree, *self.tree.findall('arkivdel')]:
            self.assertEqual(engine._numeric_buckets(node, spec), _fast_numeric_buckets(engine._numeric_buckets, node, spec))

    def test_numeric_complex_fallback(self):
        spec = dict(id='b', type='numeric_buckets', select='.//dokumentobjekt[1]/filstoerrelse',
                    buckets=[dict(id='small', min=0, max=10)])
        self.assertEqual(engine._numeric_buckets(self.tree, spec), _fast_numeric_buckets(engine._numeric_buckets, self.tree, spec))

    def test_document_parent_date_per_part(self):
        expression = 'string(ancestor::dokumentbeskrivelse[1]/opprettetDato)'
        for node in [self.tree, *self.tree.findall('arkivdel')]:
            spec = dict(id='dt', type='group_xpath', select='.//dokumentobjekt', value=expression)
            self.assertEqual(engine._group(node, spec), _fast_group(engine._group, node, spec))
            spec = dict(id='year', type='year_counts_by_node', select='.//dokumentobjekt', value=expression)
            self.assertEqual(engine._year_counts_by_node(node, spec), _fast_year_counts(engine._year_counts_by_node, node, spec))

    def test_numeric_invalid_and_overlaps(self):
        node = etree.fromstring(b'<root><n>nan</n><n>inf</n><n>-1</n><n>9</n><n> 10 </n><n> </n></root>')
        spec = dict(id='n', type='numeric_buckets', select='.//n', buckets=[
            dict(id='negative', max=0), dict(id='all'), dict(id='positive', min=9),
        ])
        self.assertEqual(engine._numeric_buckets(node, spec), _fast_numeric_buckets(engine._numeric_buckets, node, spec))


if __name__ == '__main__':
    unittest.main()
