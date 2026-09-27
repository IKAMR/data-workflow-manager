from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from lxml import etree

from noark5_workflow.analysis import xpath_test_engine as engine


class V016A13LargeXmlXpathTests(unittest.TestCase):
    def _tree(self):
        root = etree.Element("root")
        arkivdel = etree.SubElement(root, "arkivdel")
        etree.SubElement(arkivdel, "opprettetDato").text = "2020-01-01"
        for i in range(25):
            mappe = etree.SubElement(arkivdel, "mappe")
            if i % 2 == 0:
                mappe.set("type", "saksmappe")
            etree.SubElement(mappe, "saksstatus").text = "A" if i % 3 else "B"
            reg = etree.SubElement(mappe, "registrering")
            etree.SubElement(reg, "journaldato").text = f"202{i % 4}-01-01"
            db = etree.SubElement(reg, "dokumentbeskrivelse")
            etree.SubElement(db, "dokumentmedium").text = "Elektronisk arkiv"
        return etree.ElementTree(root)

    def test_large_count_subset(self):
        tree = self._tree()
        self.assertEqual(engine._xpath(tree, "count(//arkivdel//mappe)"), 25)
        self.assertEqual(engine._xpath(tree, "count(//arkivdel//registrering)"), 25)
        self.assertEqual(engine._xpath(tree, "count(//mappe[count(@*)<1])"), 12)

    def test_grouping_and_date_range(self):
        tree = self._tree()
        counts = engine._group(tree, {
            "id": "status",
            "type": "group_text",
            "select": "//mappe/saksstatus",
        })
        self.assertEqual(counts, {"A": 16, "B": 9})
        self.assertEqual(
            engine._date_range(tree, "//registrering/journaldato"),
            {"first": "2020-01-01", "last": "2023-01-01"},
        )

    def test_archive_part_reconciliation_shape_is_preserved(self):
        tree = self._tree()
        execution = {
            "metrics": [
                {"id": "folder_count", "type": "xpath", "expression": "count(//arkivdel//mappe)"},
                {"id": "status_counts", "type": "group_text", "select": "//mappe/saksstatus"},
            ],
            "archive_part_metrics": [
                {"id": "folder_count", "type": "xpath", "expression": "count(.//mappe)"},
                {"id": "status_counts", "type": "group_text", "select": ".//mappe/saksstatus"},
            ],
            "reconciliation": [
                {"id": "folder_count", "type": "scalar_sum"},
                {"id": "status_counts", "type": "counter_sum"},
            ],
        }
        values = engine._metrics_with_archive_parts(tree, execution)
        self.assertEqual(values["folder_count"], 25)
        self.assertEqual(values["_reconciliation_summary"]["status"], "match")

    def test_runtime_environment_written_to_index(self):
        # The wrapper is deliberately exercised with an empty catalogue so the
        # test stays fast while proving the a13 diagnostics are persisted.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            catalog = root / "catalog.json"
            catalog.write_text(
                '{"catalog_id":"test","source":{},"tests":[]}',
                encoding="utf-8",
            )
            out = root / "out"
            index = engine.run_catalog(catalog, root, out, include_disabled=True)
            env = index.get("runtime_environment") or {}
            self.assertIn(env.get("python_bits"), {32, 64})
            self.assertTrue(env.get("libxml2_version"))
            self.assertEqual(env.get("large_xml_mode"), "auto-iterator-cache")


if __name__ == "__main__":
    unittest.main()
