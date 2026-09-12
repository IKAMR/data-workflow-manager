import unittest

from noark5_workflow.analysis.depot_report_builder import build_depot_report_model


class A263ReportContentTests(unittest.TestCase):

    def test_additional_observed_values_become_review_point_not_technical_error(self):
        presentation = {
            "profile_id": "depot",
            "views": [{
                "id": "validation_evidence",
                "tests": [{
                    "test_id": "kdrs.f08",
                    "status": "ok",
                    "reconciliation_summary": {"status": "match"},
                    "standard_value_checks": {
                        "x": {"status": "additional_observed_values"}
                    },
                }],
            }],
        }
        model = build_depot_report_model(presentation)
        self.assertEqual(model["technical_validation"]["status"], "ok")
        self.assertEqual(
            model["standard_values"]["summary"]["status_counts"]["additional_observed_values"],
            1,
        )
        self.assertEqual(model["deviations"][0]["category"], "additional_observed_values")
        self.assertEqual(model["deviations"][0]["severity"], "review")

    def test_reconciliation_mismatch_is_serious(self):
        presentation = {
            "profile_id": "depot",
            "views": [{
                "id": "validation_evidence",
                "tests": [{
                    "test_id": "kdrs.c13",
                    "status": "ok",
                    "reconciliation_summary": {"status": "mismatch"},
                    "standard_value_checks": {},
                }],
            }],
        }
        model = build_depot_report_model(presentation)
        self.assertEqual(model["technical_validation"]["status"], "error")
        self.assertEqual(model["technical_validation"]["reconciliation"]["mismatch"], 1)
        self.assertEqual(model["deviations"][0]["category"], "reconciliation_mismatch")

    def test_summary_preserves_source_traceability(self):
        presentation = {
            "profile_id": "depot",
            "views": [{
                "id": "whole_extraction_overview",
                "sections": [{
                    "fields": [{
                        "id": "archive_count",
                        "status": "ok",
                        "value": 1,
                        "source_test_id": "kdrs.c01",
                        "source_path": "archive_count",
                    }],
                }],
            }],
        }
        model = build_depot_report_model(presentation)
        self.assertEqual(
            model["evidence"]["summary_sources"]["archive_count"],
            {"test_id": "kdrs.c01", "path": "archive_count"},
        )


if __name__ == "__main__":
    unittest.main()
