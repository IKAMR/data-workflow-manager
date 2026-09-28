from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from noark5_workflow.analysis.xpath_test_engine import run_test


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "config" / "noark5" / "tests" / "xpath_catalog_2026_05_26.json"


class V016A161XpathCompleteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.tests = {item["test_id"]: item for item in cls.catalog["tests"]}

    def test_version_is_a16(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn('VERSION = "0.1.6-a16"', text)

    def test_runtime_is_a16_1(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a16_1 import run_gui", text)

    def test_all_legacy_zero_tests_are_materialized_by_dwm(self):
        legacy_zero = [
            item for item in self.catalog["tests"]
            if item.get("legacy", {}).get("job_enabled") == 0
        ]
        self.assertTrue(legacy_zero)
        self.assertTrue(all(item.get("status") == "active" for item in legacy_zero))
        engine = (ROOT / "noark5_workflow" / "analysis" / "xpath_test_engine.py").read_text(encoding="utf-8")
        self.assertNotIn('if test["legacy"]["job_enabled"] == 0:', engine)

    def test_2026_generic_specialization_fix_is_preserved(self):
        self.assertEqual(
            self.catalog["execution_model"]["generic_specialization_rule_2026"],
            "count(@*)<1",
        )
        c08 = self.tests["kdrs.c08"]
        exprs = [m.get("expression", "") for m in c08["execution"]["metrics"]]
        self.assertTrue(any("count(@*)<1" in expr for expr in exprs))

    def test_all_five_2026_reference_files_are_registered(self):
        refs = self.catalog["source"]["reference_set"]
        self.assertEqual(len(refs), 5)
        self.assertTrue(any(name.endswith("_U1.txt") for name in refs))
        self.assertTrue(any(name.endswith("_U2.txt") for name in refs))
        self.assertTrue(any(name.endswith("_no-journal.txt") for name in refs))
        self.assertTrue(any(name.endswith("_no-offjournal.txt") for name in refs))

    def test_cross_source_documents_are_part_of_result_basis(self):
        sources = {item.get("source_xml") for item in self.catalog["tests"]}
        for name in (
            "arkivstruktur.xml",
            "arkivuttrekk.xml",
            "loependeJournal.xml",
            "offentligJournal.xml",
            "endringslogg.xml",
        ):
            self.assertIn(name, sources)

    def test_f09_explicitly_covers_noark_5(self):
        self.assertEqual(self.tests["kdrs.f09"]["noark_versions"], ["3.1", "4.0", "5.0"])

    def test_year_series_are_materialized_per_archive_part(self):
        c09 = self.tests["kdrs.c09"]["execution"]
        c16 = self.tests["kdrs.c16"]["execution"]
        c21 = self.tests["kdrs.c21"]["execution"]
        c24 = self.tests["kdrs.c24"]["execution"]
        self.assertIn("created_per_year", {m["id"] for m in c09["archive_part_metrics"]})
        self.assertIn("case_folder_created_per_year", {m["id"] for m in c09["archive_part_metrics"]})
        self.assertIn("created_per_year", {m["id"] for m in c16["archive_part_metrics"]})
        self.assertIn("journalpost_journal_date_per_year", {m["id"] for m in c16["archive_part_metrics"]})
        self.assertIn("document_description_created_per_year", {m["id"] for m in c21["archive_part_metrics"]})
        self.assertIn("document_object_parent_created_per_year", {m["id"] for m in c24["archive_part_metrics"]})

    def test_document_objects_are_counted_once_per_object_per_year(self):
        test = self.tests["kdrs.c24"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "arkivstruktur.xml").write_text(
                """<arkivstruktur><arkiv><arkivdel><systemID>A1</systemID><tittel>A</tittel>"
                "<mappe><registrering><dokumentbeskrivelse><opprettetDato>2020-01-01T00:00:00</opprettetDato>"
                "<dokumentobjekt/><dokumentobjekt/></dokumentbeskrivelse>"
                "<dokumentbeskrivelse><opprettetDato>2021-01-01T00:00:00</opprettetDato>"
                "<dokumentobjekt/></dokumentbeskrivelse></registrering></mappe>"
                "</arkivdel></arkiv></arkivstruktur>""",
                encoding="utf-8",
            )
            result = run_test(test, root)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["values"]["document_object_parent_created_per_year"],
            {"2020": 2, "2021": 1},
        )

    def test_legacy_disabled_definition_runs_when_source_exists(self):
        test = self.tests["kdrs.c11_01"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "arkivstruktur.xml").write_text(
                "<arkivstruktur><arkiv><arkivdel><klasse><klasseID>K1</klasseID><tittel>Tom</tittel></klasse></arkivdel></arkiv></arkivstruktur>",
                encoding="utf-8",
            )
            result = run_test(test, root)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["values"]["classes"][0]["class_id"], "K1")


if __name__ == "__main__":
    unittest.main()
