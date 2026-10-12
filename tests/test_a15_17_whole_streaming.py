"""a15.17: full-document // paths must match original XPath results."""
import unittest
from lxml import etree
from noark5_workflow.analysis import xpath_fast_a154 as fast
from noark5_workflow.analysis import xpath_test_engine as engine


class WholeDocumentStreamingTests(unittest.TestCase):
    def setUp(self):
        self.tree = etree.ElementTree(etree.fromstring(
            b'<arkiv><arkivdel><mappe type="a"><opprettetDato>2023-01-01</opprettetDato>'
            b'<filstoerrelse>10</filstoerrelse><filstoerrelse>200</filstoerrelse></mappe>'
            b'<mappe type="b"><opprettetDato>2021-11-10</opprettetDato>'
            b'<filstoerrelse>5</filstoerrelse></mappe></arkivdel></arkiv>'
        ))
        self.part = self.tree.xpath('//arkivdel')[0]

    def test_whole_dates(self):
        for path in ('//mappe/opprettetDato', './/mappe/opprettetDato'):
            self.assertEqual(engine._date_range(self.tree, path),
                             fast._fast_date_range(engine._date_range, self.tree, path))

    def test_whole_years(self):
        for path in ('//mappe/opprettetDato', './/mappe/opprettetDato'):
            self.assertEqual(engine._year_counts(self.tree, path),
                             fast._fast_year_counts_text(engine._year_counts, self.tree, path))

    def test_whole_text_groups(self):
        for path in ('//mappe/opprettetDato', './/mappe/opprettetDato'):
            spec = {'type': 'group_text', 'select': path}
            self.assertEqual(engine._group(self.tree, spec),
                             fast._fast_group(engine._group, self.tree, spec))

    def test_whole_numeric_stats(self):
        for path in ('//filstoerrelse', './/filstoerrelse'):
            self.assertEqual(engine._numeric_stats(self.tree, path),
                             fast._fast_numeric_stats(engine._numeric_stats, self.tree, path))

    def test_whole_numeric_buckets(self):
        for path in ('//filstoerrelse', './/filstoerrelse'):
            spec = {'type': 'numeric_buckets', 'select': path, 'buckets': [
                {'id': 'small', 'min': 0, 'max': 9},
                {'id': 'middle', 'min': 10, 'max': 99},
                {'id': 'large', 'min': 100, 'max': None}]}
            self.assertEqual(engine._numeric_buckets(self.tree, spec),
                             fast._fast_numeric_buckets(engine._numeric_buckets, self.tree, spec))

    def test_relative_archive_part_not_promoted_to_global(self):
        self.assertIsNone(fast._streamable_path(self.part, '//mappe'))
        self.assertEqual(engine._date_range(self.part, '//mappe/opprettetDato'),
                         fast._fast_date_range(engine._date_range, self.part,
                                               '//mappe/opprettetDato'))

    def test_document_root_candidate_falls_back(self):
        tree = etree.ElementTree(etree.fromstring(b'<dt>2022-01-01<dt>2001-01-01</dt></dt>'))
        self.assertIsNone(fast._streamable_path(tree, '//dt'))
        self.assertEqual(engine._date_range(tree, '//dt'),
                         fast._fast_date_range(engine._date_range, tree, '//dt'))

    def test_predicates_keep_original(self):
        self.assertIsNone(fast._streamable_path(self.tree, '//mappe[1]/opprettetDato'))
        self.assertEqual(engine._date_range(self.tree, '//mappe[1]/opprettetDato'),
                         fast._fast_date_range(engine._date_range, self.tree,
                                               '//mappe[1]/opprettetDato'))


if __name__ == '__main__':
    unittest.main()
