import unittest

from noark5_workflow.analysis.depot_report_builder import build_depot_report_model


class A26DepotReportTests(unittest.TestCase):

    def test_report_uses_materialized_depot_presentation(self):
        presentation = {
            "profile_id": "depot",
            "views": [
                {
                    "id": "whole_extraction_overview",
                    "sections": [{
                        "fields": [
                            {"id":"archive_count","status":"ok","value":1},
                            {"id":"archive_part_count","status":"ok","value":5},
                            {"id":"folder_count","status":"ok","value":10},
                        ]
                    }]
                },
                {
                    "id": "archive_part_overview",
                    "archive_parts": [{
                        "archive_part":{"system_id":"A"},
                        "sections":[{
                            "fields":[
                                {"id":"folder_count","status":"ok","value":3}
                            ]
                        }]
                    }]
                },
                {
                    "id":"validation_evidence",
                    "tests":[
                        {"test_id":"kdrs.c01","status":"ok","standard_value_checks":{}},
                        {"test_id":"kdrs.x","status":"disabled_by_legacy_source","standard_value_checks":{}},
                    ]
                },
                {
                    "id":"depot_control_summary",
                    "sections":[]
                }
            ]
        }
        model = build_depot_report_model(
            presentation,
            source_presentation_file="depot.json",
        )
        self.assertEqual(model["summary"]["archive_count"], 1)
        self.assertEqual(model["summary"]["archive_part_count"], 5)
        self.assertEqual(model["technical_validation"]["summary"]["ok"], 1)
        self.assertEqual(model["technical_validation"]["summary"]["legacy_disabled"], 1)
        self.assertEqual(model["archive_parts"][0]["folder_count"], 3)
        self.assertEqual(model["assessment"]["status"], "requires_clarification")

    def test_report_does_not_auto_accept_content(self):
        presentation = {"profile_id":"depot","views":[]}
        model = build_depot_report_model(presentation)
        self.assertNotEqual(model["assessment"]["status"], "accepted")
        self.assertIn(
            "Arkivskaper",
            model["assessment"]["archive_creator_responsibility"],
        )



if __name__ == "__main__":
    unittest.main()
