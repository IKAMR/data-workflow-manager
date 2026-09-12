import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.view_composer import compose_views

ROOT = Path(__file__).parents[1]

class A253PresentationProfileTests(unittest.TestCase):

    def test_view_definition_has_audiences_and_groups(self):
        definition = json.loads(
            (ROOT / "config/noark5/views/canonical_views.json").read_text(encoding="utf-8")
        )
        self.assertIn("depot", definition["audiences"])
        self.assertIn("archive_creator", definition["audiences"])
        self.assertIn("final_report", definition["audiences"])
        self.assertIn("presentation_groups", definition)

    def test_presentation_profiles_are_profile_discoverable(self):
        profile = json.loads(
            (ROOT / "config/noark5/profile.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            profile["presentation"]["profiles"],
            "config/noark5/views/presentation_profiles.json",
        )
        self.assertEqual(
            profile["definitions"]["views"],
            ["config/noark5/views/canonical_views.json"],
        )

    def test_composer_preserves_presentation_metadata_without_recalculation(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            (run / "results").mkdir()
            (run / "index.json").write_text(
                json.dumps({"execution_profile":"normal","summary":{"ok":1}}),
                encoding="utf-8",
            )
            (run / "results/kdrs_c01.json").write_text(
                json.dumps({"test_id":"kdrs.c01","values":{"archive_count":1}}),
                encoding="utf-8",
            )
            definition = {
                "audiences":{"depot":{"label":"Depot"}},
                "presentation_groups":{"g":{"label":"G","order":10}},
                "section_library":{
                    "s":{
                        "label":"S",
                        "presentation_group":"g",
                        "fields":[
                            {
                                "id":"archive_count",
                                "label":"Arkiv",
                                "source_test":"kdrs.c01",
                                "source_path":"archive_count",
                                "presentation_order":10,
                                "visible_for":["depot"]
                            }
                        ]
                    }
                },
                "compositions":[
                    {
                        "id":"whole",
                        "label":"Whole",
                        "scope":"whole_extraction",
                        "sections":["s"],
                        "audiences":["depot"],
                        "presentation_order":10
                    }
                ]
            }
            out = compose_views(run, definition)
            view = out["views"][0]
            self.assertEqual(view["audiences"], ["depot"])
            self.assertEqual(view["sections"][0]["presentation_group"], "g")
            self.assertEqual(view["sections"][0]["fields"][0]["value"], 1)

if __name__ == "__main__":
    unittest.main()
