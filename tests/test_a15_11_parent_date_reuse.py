from __future__ import annotations

import unittest
from lxml import etree
from noark5_workflow.analysis import xpath_fast_a154 as fast
from noark5_workflow.analysis import xpath_test_engine as engine

DATE = "string(ancestor::dokumentbeskrivelse[1]/opprettetDato)"


class A1511ParentDateReuseTests(unittest.TestCase):
    def setUp(self):
        fast._parent_date_summaries.clear()
        self.root = etree.fromstring(b'''<arkiv>
          <arkivdel><dokumentbeskrivelse><opprettetDato>2022-03-01</opprettetDato>
            <dokumentobjekt/><dokumentobjekt/></dokumentbeskrivelse>
            <dokumentbeskrivelse><opprettetDato>not-a-date</opprettetDato>
              <dokumentobjekt/></dokumentbeskrivelse></arkivdel>
          <arkivdel><dokumentbeskrivelse><opprettetDato>2020-01-01</opprettetDato>
            <dokumentobjekt/></dokumentbeskrivelse></arkivdel>
        </arkiv>''')

    def tearDown(self):
        fast._parent_date_summaries.clear()

    def test_both_metrics_match_engine_whole_and_parts(self):
        for node in [self.root, *self.root.findall('arkivdel')]:
            for sel in ('.//dokumentobjekt',):
                group = {'type': 'group_xpath', 'select': sel, 'value': DATE}
                years = {'type': 'year_counts_by_node', 'select': sel, 'value': DATE}
                self.assertEqual(engine._group(node, group), fast._fast_group(engine._group, node, group))
                self.assertEqual(engine._year_counts_by_node(node, years), fast._fast_year_counts(engine._year_counts_by_node, node, years))

    def test_one_traversal_and_counter_copy(self):
        group = {'type': 'group_xpath', 'select': './/dokumentobjekt', 'value': DATE}
        years = {'type': 'year_counts_by_node', 'select': './/dokumentobjekt', 'value': DATE}
        original = fast._parent_created
        calls = []
        try:
            def counted(node):
                calls.append(node)
                return original(node)
            fast._parent_created = counted
            values = fast._fast_group(engine._group, self.root, group)
            values.clear()
            self.assertEqual({'2022': 2, '2020': 1}, fast._fast_year_counts(engine._year_counts_by_node, self.root, years))
            self.assertEqual(4, len(calls))
            self.assertEqual({'2020-01-01': 1, '2022-03-01': 2, 'not-a-date': 1},
                             fast._fast_group(engine._group, self.root, group))
            self.assertEqual(4, len(calls))
        finally:
            fast._parent_created = original

    def test_distinct_archive_parts_do_not_share_results(self):
        parts = self.root.findall('arkivdel')
        self.assertEqual({'2022': 2}, fast._parent_created_summary(parts[0], './/dokumentobjekt')[1])
        self.assertEqual({'2020': 1}, fast._parent_created_summary(parts[1], './/dokumentobjekt')[1])
        self.assertEqual(2, len(fast._parent_date_summaries))

    def test_scoped_cache_cleared_even_on_error(self):
        from noark5_workflow.analysis import xpath_diagnostics
        original = fast._run_catalog_profiled
        old_run = engine.run_test
        def fake_catalog(*args, **kwargs):
            engine.run_test(None, None)
        def fake_test(*args, **kwargs):
            fast._parent_created_summary(self.root, './/dokumentobjekt')
            raise ValueError('simulated error')
        try:
            fast._run_catalog_profiled = fake_catalog
            engine.run_test = fake_test
            with self.assertRaisesRegex(ValueError, 'simulated error'):
                fast.run_catalog_profiled()
            self.assertEqual({}, fast._parent_date_summaries)
            self.assertIs(engine.run_test, fake_test)
        finally:
            fast._run_catalog_profiled = original
            engine.run_test = old_run

    def test_other_expressions_fallback_unchanged(self):
        spec = {'type': 'group_xpath', 'select': './/dokumentobjekt[1]', 'value': DATE}
        self.assertEqual(engine._group(self.root, spec), fast._fast_group(engine._group, self.root, spec))

if __name__ == '__main__':
    unittest.main()
