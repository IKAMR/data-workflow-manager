from __future__ import annotations

import unittest
from lxml import etree
from noark5_workflow.analysis import xpath_test_engine as engine
from noark5_workflow.analysis.xpath_fast_a154 import _fast_numeric_buckets


class A155NumericBucketTests(unittest.TestCase):
    def setUp(self):
        self.root = etree.fromstring(b"""<arkiv><arkivdel>
            <filstoerrelse>0</filstoerrelse>
            <filstoerrelse>1</filstoerrelse>
            <filstoerrelse>9</filstoerrelse>
            <filstoerrelse>10</filstoerrelse>
            <filstoerrelse>99.5</filstoerrelse>
            <filstoerrelse>100</filstoerrelse>
            <filstoerrelse>12345678</filstoerrelse>
            <filstoerrelse>bad</filstoerrelse>
            <filstoerrelse></filstoerrelse>
        </arkivdel></arkiv>""")
        self.spec = {
            "id": "file_size_buckets", "type": "numeric_buckets", "select": "//filstoerrelse",
            "buckets": [
                {"id": "zero", "min": 0, "max": 0},
                {"id": "small", "min": 1, "max": 9},
                {"id": "large", "min": 10, "max": None},
                {"id": "overlap", "min": 0, "max": 100},
                {"id": "any", "min": None, "max": None},
            ],
        }

    def test_matches_original_whole_extraction(self):
        self.assertEqual(engine._numeric_buckets(self.root, self.spec),
                         _fast_numeric_buckets(engine._numeric_buckets, self.root, self.spec))

    def test_matches_original_per_archive_part(self):
        spec = dict(self.spec, select=".//filstoerrelse")
        part = self.root.find("arkivdel")
        self.assertEqual(engine._numeric_buckets(part, spec),
                         _fast_numeric_buckets(engine._numeric_buckets, part, spec))

    def test_empty_values_and_zero_buckets(self):
        empty = etree.fromstring(b"<arkiv/>")
        for specs in (self.spec, dict(self.spec, buckets=[])):
            self.assertEqual(engine._numeric_buckets(empty, specs),
                             _fast_numeric_buckets(engine._numeric_buckets, empty, specs))

    def test_no_change_after_run(self):
        # The wrapper restores the original function even when a catalogue run fails.
        from noark5_workflow.analysis.xpath_fast_a154 import run_catalog_profiled
        original = engine._numeric_buckets
        with self.assertRaises(RuntimeError):
            run_catalog_profiled("/nonexistent/a155.json", "/nonexistent", "/nonexistent/out")
        self.assertIs(original, engine._numeric_buckets)


if __name__ == "__main__":
    unittest.main()
