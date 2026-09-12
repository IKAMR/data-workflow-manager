import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.view_composer import compose_views

ROOT = Path(__file__).parents[1]

class A25ViewCompositionTests(unittest.TestCase):

    def test_view_definition_uses_reusable_sections(self):
        definition = json.loads(
            (ROOT / "config/noark5/views/canonical_views.json").read_text(encoding="utf-8")
        )
        self.assertIn("section_library", definition)
        self.assertIn("compositions", definition)
        self.assertTrue(definition["principles"]["no_xpath_in_views"])
        self.assertTrue(definition["principles"]["no_duplicate_calculation_logic"])

    def test_profile_has_only_one_views_operation_definition(self):
        profile_text = (ROOT / "noark5_workflow/profile.py").read_text(encoding="utf-8")
        self.assertEqual(profile_text.count("ComposeNoark5ViewsOperation,"), 2)
        self.assertNotIn("RunNoark5ViewsOperation", profile_text)

    def test_composer_reads_canonical_results_only(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            (run / "results").mkdir()
            (run / "index.json").write_text(
                json.dumps({"execution_profile":"normal","summary":{"ok":1}}),
                encoding="utf-8",
            )
            (run / "results/kdrs_c01.json").write_text(
                json.dumps({"values":{"archive_count":1}}), encoding="utf-8"
            )
            (run / "results/kdrs_c02.json").write_text(
                json.dumps({"values":{"_archive_parts":[
                    {"archive_part":{"system_id":"A"},"values":{"archive_part_count":1}}
                ]}}), encoding="utf-8"
            )

            definition = {
                "section_library":{
                    "s":{"label":"S","fields":[
                        {"id":"archive_count","source_test":"kdrs.c01","source_path":"archive_count","value_type":"integer"}
                    ]}
                },
                "compositions":[
                    {"id":"whole","label":"Whole","scope":"whole_extraction","sections":["s"]}
                ]
            }
            out = compose_views(run, definition)
            field = next(v for v in out["views"] if v["id"] == "whole")["sections"][0]["fields"][0]
            self.assertEqual(field["status"], "ok")
            self.assertEqual(field["value"], 1)

    def test_composer_reports_missing_source_explicitly(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            (run / "results").mkdir()
            (run / "index.json").write_text(
                json.dumps({"execution_profile":"normal"}), encoding="utf-8"
            )
            definition = {
                "section_library":{
                    "s":{"fields":[
                        {"id":"x","source_test":"kdrs.missing","source_path":"x"}
                    ]}
                },
                "compositions":[
                    {"id":"whole","label":"Whole","scope":"whole_extraction","sections":["s"]}
                ]
            }
            out = compose_views(run, definition)
            field = next(v for v in out["views"] if v["id"] == "whole")["sections"][0]["fields"][0]
            self.assertEqual(field["status"], "source_missing")

if __name__ == "__main__":
    unittest.main()
