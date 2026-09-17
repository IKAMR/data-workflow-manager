import unittest
from pathlib import Path

from gui.depot_result_views import (
    archive_part_label,
    archive_part_view_text,
    review_points_view_text,
    technical_view_text,
    total_view_text,
)

ROOT = Path(__file__).resolve().parents[1]


class A5DepotResultViewsTests(unittest.TestCase):
    def test_total_view_uses_materialized_summary_and_evidence(self):
        model = {
            "summary": {"archive_count": 1, "archive_part_count": 5, "document_object_count": 3906},
            "evidence": {"source_presentation_profile": "depot", "source_presentation_file": "x/depot.json"},
        }
        text = total_view_text(model)
        self.assertIn("Arkiv: 1", text)
        self.assertIn("Arkivdeler: 5", text)
        self.assertIn("Dokumentobjekter: 3906", text)
        self.assertIn("Presentasjonsprofil: depot", text)

    def test_technical_view_reads_existing_test_rows(self):
        model = {
            "technical_validation": {
                "status": "ok",
                "summary": {"ok": 52, "error": 0, "legacy_disabled": 5, "other": 0},
                "reconciliation": {"match": 18, "mismatch": 0, "not_comparable": 0, "other": 0},
                "tests": [{"test_id": "C01", "legacy_job_id": "U1", "test_point": "Arkiv", "status": "ok"}],
            }
        }
        text = technical_view_text(model)
        self.assertIn("OK 52", text)
        self.assertIn("match 18", text)
        self.assertIn("C01", text)
        self.assertIn("U1", text)

    def test_archive_part_view_exposes_counts_and_traceability(self):
        row = {
            "archive_part": {"system_id": "ap-1", "title": "Sakarkiv"},
            "folder_count": 100,
            "registration_count": 250,
            "document_object_count": 400,
            "sources": {"folder_count": {"test_id": "C02", "path": "archive_parts.ap-1.folder_count"}},
        }
        self.assertEqual(archive_part_label(row, 0), "1. Sakarkiv [ap-1]")
        text = archive_part_view_text(row)
        self.assertIn("Mapper: 100", text)
        self.assertIn("Registreringer: 250", text)
        self.assertIn("Dokumentobjekter: 400", text)
        self.assertIn("C02", text)

    def test_review_points_view_preserves_deviations_and_standard_values(self):
        model = {
            "deviations": [{"severity": "review", "summary": "Observerte tilleggsverdier", "note": "Må vurderes."}],
            "standard_values": {
                "summary": {
                    "tests_with_checks": 7,
                    "status_counts": {
                        "all_observed_values_standard": 10,
                        "additional_observed_values": 2,
                        "no_observed_values": 1,
                        "other": 0,
                    },
                }
            },
        }
        text = review_points_view_text(model)
        self.assertIn("Observerte tilleggsverdier", text)
        self.assertIn("Tilleggsverdier observert: 2", text)
        self.assertIn("Tester med kontroller: 7", text)

    def test_assessment_dialog_opens_specialized_result_views(self):
        dialog = (ROOT / "gui" / "depot_assessment_dialog.py").read_text(encoding="utf-8")
        views = (ROOT / "gui" / "depot_result_views.py").read_text(encoding="utf-8")
        self.assertIn('text="Resultatvisninger"', dialog)
        self.assertIn("DepotResultViewsDialog", dialog)
        self.assertIn("self.report_model = model", dialog)
        for tab in ("Totalt", "Teknisk", "Arkivdeler", "Vurderingspunkter"):
            self.assertIn(f'"{tab}"', views)


if __name__ == "__main__":
    unittest.main()
