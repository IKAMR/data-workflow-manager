import unittest

from noark5_workflow.analysis.presentation_materializer import (
    materialize_presentation_profile,
)


class A25PresentationMaterializationTests(unittest.TestCase):

    def setUp(self):
        self.views = [
            {
                "id": "whole",
                "label": "Whole",
                "audiences": ["depot", "archive_creator", "final_report"],
                "presentation_order": 10,
                "sections": [
                    {
                        "id": "s",
                        "fields": [
                            {
                                "id": "common",
                                "value": 1,
                                "visible_for": ["depot", "archive_creator", "final_report"],
                                "source_test_id": "kdrs.c01",
                                "source_path": "archive_count",
                            },
                            {
                                "id": "depot_only",
                                "value": 2,
                                "visible_for": ["depot"],
                                "source_test_id": "kdrs.c02",
                                "source_path": "archive_part_count",
                            },
                        ],
                    }
                ],
            },
            {
                "id": "validation",
                "label": "Validation",
                "audiences": ["depot"],
                "presentation_order": 20,
                "sections": [],
            },
        ]
        self.definition = {
            "profiles": {
                "depot": {
                    "label": "Depot",
                    "include_audience": "depot",
                    "include_views": ["whole", "validation"],
                },
                "archive_creator": {
                    "label": "Arkivskaper",
                    "include_audience": "archive_creator",
                    "include_views": ["whole"],
                },
            }
        }

    def test_depot_gets_depot_fields_and_views(self):
        out = materialize_presentation_profile(
            self.views,
            "depot",
            self.definition,
        )
        self.assertEqual([v["id"] for v in out["views"]], ["whole", "validation"])
        fields = out["views"][0]["sections"][0]["fields"]
        self.assertEqual({f["id"] for f in fields}, {"common", "depot_only"})

    def test_archive_creator_filters_depot_only_field(self):
        out = materialize_presentation_profile(
            self.views,
            "archive_creator",
            self.definition,
        )
        self.assertEqual([v["id"] for v in out["views"]], ["whole"])
        fields = out["views"][0]["sections"][0]["fields"]
        self.assertEqual([f["id"] for f in fields], ["common"])
        self.assertEqual(fields[0]["source_test_id"], "kdrs.c01")
        self.assertEqual(fields[0]["source_path"], "archive_count")

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            materialize_presentation_profile(
                self.views,
                "missing",
                self.definition,
            )


if __name__ == "__main__":
    unittest.main()
