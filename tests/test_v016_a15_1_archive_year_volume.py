from pathlib import Path
import json
import unittest

from lxml import etree
from noark5_workflow.analysis.xpath_test_engine import _eval_metrics
from noark5_workflow.analysis.depot_report_builder import build_depot_report_model

ROOT = Path(__file__).resolve().parents[1]


class V016A151ArchiveYearVolumeTests(unittest.TestCase):
    def test_catalog_materializes_document_year_distributions(self):
        data = json.loads((ROOT / "config/noark5/tests/xpath_catalog_2026_05_26.json").read_text(encoding="utf-8"))
        by_id = {row["test_id"]: row for row in data["tests"]}
        c21 = by_id["kdrs.c21"]["execution"]
        c24 = by_id["kdrs.c24"]["execution"]
        self.assertTrue(any(x.get("id") == "document_description_created_per_year" for x in c21["archive_part_metrics"]))
        self.assertTrue(any(x.get("id") == "document_object_parent_created_counts" for x in c24["archive_part_metrics"]))

    def test_document_object_year_uses_parent_document_description_date(self):
        xml = etree.fromstring(b"""<arkivdel><dokumentbeskrivelse><opprettetDato>2020-01-02T00:00:00</opprettetDato><dokumentobjekt/><dokumentobjekt/></dokumentbeskrivelse><dokumentbeskrivelse><opprettetDato>2021-03-04T00:00:00</opprettetDato><dokumentobjekt/></dokumentbeskrivelse></arkivdel>""")
        values = _eval_metrics(xml, [{
            "id": "objects",
            "type": "group_xpath",
            "select": ".//dokumentobjekt",
            "value": "string(ancestor::dokumentbeskrivelse[1]/opprettetDato)",
        }])
        self.assertEqual(values["objects"], {
            "2020-01-02T00:00:00": 2,
            "2021-03-04T00:00:00": 1,
        })

    def test_archive_part_view_exposes_four_year_series(self):
        data = json.loads((ROOT / "config/noark5/views/canonical_views.json").read_text(encoding="utf-8"))
        fields = {row["id"]: row for row in data["section_library"]["yearly_volume"]["fields"]}
        self.assertEqual(
            set(fields),
            {
                "folder_created_per_year",
                "journal_date_per_year",
                "document_description_created_per_year",
                "document_object_created_per_year",
            },
        )
        archive = next(x for x in data["compositions"] if x["id"] == "archive_part_overview")
        self.assertIn("yearly_volume", archive["sections"])

    def test_report_model_preserves_reported_period_and_normalizes_years(self):
        presentation = {
            "views": [
                {"id": "whole_extraction_overview", "sections": []},
                {
                    "id": "archive_part_overview",
                    "archive_parts": [
                        {
                            "archive_part": {
                                "system_id": "AP-1",
                                "archive_period_start_date": "2004-01-01",
                                "archive_period_end_date": "2023-12-31",
                            },
                            "sections": [
                                {
                                    "fields": [
                                        {"id": "folder_created_per_year", "status": "ok", "value": {"2005": 2}},
                                        {"id": "journal_date_per_year", "status": "ok", "value": {"2006": 3}},
                                        {"id": "document_description_created_per_year", "status": "ok", "value": {"2007": 4}},
                                        {"id": "document_object_created_per_year", "status": "ok", "value": {"2008-02-03T10:00:00": 2, "2008-06-01T10:00:00": 5}},
                                    ]
                                }
                            ],
                        }
                    ],
                },
                {"id": "validation_evidence", "tests": []},
                {"id": "depot_control_summary", "sections": []},
            ]
        }
        model = build_depot_report_model(presentation)
        row = model["archive_parts"][0]
        self.assertEqual(row["archive_part"]["archive_period_start_date"], "2004-01-01")
        self.assertEqual(row["yearly_volume"]["folder"], {"2005": 2})
        self.assertEqual(row["yearly_volume"]["journal"], {"2006": 3})
        self.assertEqual(row["yearly_volume"]["document_description"], {"2007": 4})
        self.assertEqual(row["yearly_volume"]["document_object"], {"2008": 7})

    def test_gui_is_compact_and_compares_reported_and_observed_period(self):
        source = (ROOT / "gui/depot_result_center_a15_1.py").read_text(encoding="utf-8")
        self.assertIn('text="Omfang per år"', source)
        self.assertIn('"Mappe/sak"', source)
        self.assertIn('"Registrering/JP"', source)
        self.assertIn('"Dok.beskrivelse"', source)
        self.assertIn('"Dok.objekt"', source)
        self.assertIn('f"Oppgitt: {self._period_text(reported)}"', source)
        self.assertIn('f"Observert: {self._period_text(observed)}"', source)
        self.assertIn('height=154', source)

    def test_runtime_and_version_are_a15(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a15_1 import run_gui", main)
        self.assertIn('VERSION = "0.1.6-a15"', version)


if __name__ == "__main__":
    unittest.main()
