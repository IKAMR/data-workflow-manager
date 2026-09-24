import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.depot_report_builder import (
    build_depot_report_model,
    write_depot_report_html,
)


class V016A1ArchivePartReportTests(unittest.TestCase):

    def test_html_prioritizes_archive_parts_without_changing_report_model(self):
        presentation = {
            "profile_id": "depot",
            "views": [
                {
                    "id": "whole_extraction_overview",
                    "sections": [{"fields": [
                        {"id": "archive_part_count", "status": "ok", "value": 2},
                        {"id": "folder_count", "status": "ok", "value": 31},
                        {"id": "registration_count", "status": "ok", "value": 410},
                        {"id": "document_object_count", "status": "ok", "value": 500},
                    ]}],
                },
                {
                    "id": "archive_part_overview",
                    "archive_parts": [
                        {
                            "archive_part": {"system_id": "A1", "title": "Sakarkiv"},
                            "sections": [{"fields": [
                                {"id": "folder_count", "status": "ok", "value": 20, "source_test_id": "kdrs.x"},
                                {"id": "registration_count", "status": "ok", "value": 300},
                            ]}],
                        },
                        {
                            "archive_part": {"system_id": "A2", "title": "Personalarkiv"},
                            "sections": [{"fields": [
                                {"id": "folder_count", "status": "ok", "value": 11},
                                {"id": "registration_count", "status": "ok", "value": 110},
                            ]}],
                        },
                    ],
                },
                {
                    "id": "validation_evidence",
                    "tests": [{"test_id": "kdrs.c01", "status": "ok", "standard_value_checks": {}}],
                },
            ],
        }
        model = build_depot_report_model(presentation, source_presentation_file="depot.json")
        self.assertEqual(model["depot_report_model_format_version"], 2)
        self.assertEqual(len(model["archive_parts"]), 2)

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.html"
            write_depot_report_html(model, target)
            rendered = target.read_text(encoding="utf-8")

        self.assertIn("Vurdering av arkivuttrekk", rendered)
        self.assertIn("Arkivdelene er hovedinngangen", rendered)
        self.assertIn("Sakarkiv", rendered)
        self.assertIn("Personalarkiv", rendered)
        self.assertIn("systemID: A1", rendered)
        self.assertLess(rendered.index("<h2>Arkivdeler</h2>"), rendered.index("<h2>Kontroll og vurderingsgrunnlag</h2>"))
        self.assertIn("Ekstern evidens holdes separat fra DWM-masterresultater", rendered)


if __name__ == "__main__":
    unittest.main()
