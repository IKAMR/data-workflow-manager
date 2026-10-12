from collections import OrderedDict
import unittest
from lxml import etree
from noark5_workflow.analysis import xpath_fast_a154 as fast
from noark5_workflow.analysis import xpath_test_engine as engine


class A1516ArchivePartReuseTests(unittest.TestCase):
    def setUp(self):
        self.tree = etree.ElementTree(etree.fromstring(
            '<arkiv><arkivdel><mappe/><mappe/><saksstatus>A</saksstatus></arkivdel>'
            '<arkivdel><mappe/><saksstatus>B</saksstatus></arkivdel></arkiv>'))
        self.specs = [
            {'id': 'n', 'type': 'xpath', 'expression': 'count(.//mappe)'},
            {'id': 's', 'type': 'group_text', 'select': './/saksstatus'},
        ]

    def test_independent_archive_parts_and_reuse(self):
        cache = OrderedDict()
        calls = []
        def compute(node, specs):
            calls.append((node, tuple(s['id'] for s in specs)))
            return engine._eval_metrics(node, specs)
        parts = self.tree.xpath('//arkivdel')
        first = fast._shared_eval_metrics(compute, cache, 'arkivstruktur.xml', parts[0], self.specs, part_index=1)
        second = fast._shared_eval_metrics(compute, cache, 'arkivstruktur.xml', parts[1], self.specs, part_index=2)
        again = fast._shared_eval_metrics(compute, cache, 'arkivstruktur.xml', parts[0], self.specs, part_index=1)
        self.assertEqual(first, again)
        self.assertEqual(first['n'], 2)
        self.assertEqual(second['n'], 1)
        self.assertEqual(len(calls), 4)
        self.assertEqual(len(cache), 4)

    def test_source_scope_and_unscoped_fallback(self):
        cache = OrderedDict()
        calls = []
        def compute(node, specs):
            calls.append(1)
            return engine._eval_metrics(node, specs)
        part = self.tree.xpath('//arkivdel')[0]
        for source, index in [('one.xml', 1), ('other.xml', 1), ('one.xml', 2)]:
            fast._shared_eval_metrics(compute, cache, source, part, self.specs, part_index=index)
        self.assertEqual(len(calls), 6)
        fast._shared_eval_metrics(compute, cache, 'one.xml', part, self.specs)
        self.assertEqual(len(calls), 7)

    def test_whole_is_not_same_as_part(self):
        cache = OrderedDict()
        whole = fast._shared_eval_metrics(engine._eval_metrics, cache, 'a.xml', self.tree, self.specs)
        part = fast._shared_eval_metrics(engine._eval_metrics, cache, 'a.xml', self.tree.xpath('//arkivdel')[0], self.specs, part_index=1)
        self.assertEqual(whole['n'], 3)
        self.assertEqual(part['n'], 2)
        self.assertEqual(len(cache), 4)

    def test_cache_is_bounded(self):
        cache = OrderedDict()
        for index in range(1, 145):
            fast._shared_eval_metrics(engine._eval_metrics, cache, 'a.xml', self.tree.xpath('//arkivdel')[0], [self.specs[0]], part_index=index)
        self.assertLessEqual(len(cache), fast._SHARED_METRIC_LIMIT)


if __name__ == '__main__':
    unittest.main()
