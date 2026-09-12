import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.view_composer import compose_views

ROOT = Path(__file__).parents[1]


class A253PresentationFixTests(unittest.TestCase):

    def test_validation_evidence_preserves_audience_and_order(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            (run / "results").mkdir()
            (run / "index.json").write_text(
                json.dumps({
                    "execution_profile": "normal",
                    "summary": {"ok": 1},
                    "tests": [],
                }),
                encoding="utf-8",
            )
            definition = {
                "section_library": {},
                "compositions": [{
                    "id": "validation_evidence",
                    "label": "Validering og evidens",
                    "scope": "whole_extraction",
                    "sections": ["validation_summary"],
                    "audiences": ["depot"],
                    "presentation_order": 30,
                }],
            }
            out = compose_views(run, definition)
            view = out["views"][0]
            self.assertEqual(view["id"], "validation_evidence")
            self.assertEqual(view["audiences"], ["depot"])
            self.assertEqual(view["presentation_order"], 30)

    def test_archive_part_sections_preserve_presentation_group(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            (run / "results").mkdir()
            (run / "index.json").write_text(
                json.dumps({"execution_profile": "normal"}),
                encoding="utf-8",
            )
            (run / "results" / "kdrs_c02.json").write_text(
                json.dumps({
                    "test_id": "kdrs.c02",
                    "values": {
                        "_archive_parts": [{
                            "archive_part": {"system_id": "A"},
                            "values": {"folder_count": 3},
                        }]
                    },
                }),
                encoding="utf-8",
            )
            definition = {
                "section_library": {
                    "content_summary": {
                        "label": "Innhold",
                        "presentation_group": "content_volume",
                        "fields": [{
                            "id": "folder_count",
                            "label": "Mapper",
                            "source_test": "kdrs.c02",
                            "source_path": "folder_count",
                            "presentation_order": 10,
                            "visible_for": ["depot"],
                        }],
                    }
                },
                "compositions": [{
                    "id": "archive_part_overview",
                    "label": "Oversikt per arkivdel",
                    "scope": "archive_part",
                    "sections": ["content_summary"],
                    "audiences": ["depot"],
                    "presentation_order": 20,
                }],
            }
            out = compose_views(run, definition)
            section = out["views"][0]["archive_parts"][0]["sections"][0]
            self.assertEqual(section["presentation_group"], "content_volume")


if __name__ == "__main__":
    unittest.main()
