import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.depot_annotations import (
    list_depot_annotations,
    record_depot_annotation,
)
from noark5_workflow.core.identity import UserIdentity

ROOT = Path(__file__).resolve().parents[1]


class A7AnnotationOverviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.report = self.root / "depot_validation_report.json"
        self.report.write_text(
            json.dumps({"report_type": "noark5_depot_validation"}),
            encoding="utf-8",
        )
        self.alice = UserIdentity("u-1", "alice", "Alice", "alice@example.invalid")
        self.bob = UserIdentity("u-2", "bob", "Bob", "bob@example.invalid")

        record_depot_annotation(
            self.report,
            annotation_type="note",
            text="Generell merknad om totalbildet",
            user=self.alice,
            view_id="total",
            target_type="view",
            target_id="total",
            target_label="Totaloversikt",
        )
        record_depot_annotation(
            self.report,
            annotation_type="deviation",
            text="Avvik i arkivdel Sakarkiv",
            user=self.bob,
            view_id="archive_parts",
            target_type="archive_part",
            target_id="ap-1",
            target_label="Sakarkiv [ap-1]",
        )
        record_depot_annotation(
            self.report,
            annotation_type="question",
            text="Må dette avklares med arkivskaper?",
            user=self.alice,
            view_id="technical",
            target_type="view",
            target_id="technical",
            target_label="Teknisk validering",
            status="resolved",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_filters_support_type_status_and_user(self):
        rows = list_depot_annotations(
            self.report,
            annotation_type="question",
            status="resolved",
            username="alice",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["text"], "Må dette avklares med arkivskaper?")

    def test_text_search_is_case_insensitive_and_searches_target_label(self):
        rows = list_depot_annotations(self.report, text_search="SAKARKIV")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["target"]["target_id"], "ap-1")

    def test_combined_filters_can_select_one_subview_comment(self):
        rows = list_depot_annotations(
            self.report,
            view_id="archive_parts",
            target_id="ap-1",
            annotation_type="deviation",
            username="bob",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["annotation_type"], "deviation")

    def test_gui_exposes_all_comments_and_filter_controls(self):
        text = (ROOT / "gui" / "depot_result_views.py").read_text(encoding="utf-8")
        self.assertIn("class DepotAnnotationOverviewDialog", text)
        self.assertIn('text="Alle kommentarer..."', text)
        for label in ("Type", "Status", "Visning", "Del / mål", "Bruker"):
            self.assertIn(f'"{label}"', text)
        self.assertIn("text_search=self.search_entry.get()", text)

    def test_filtering_remains_cli_neutral_in_analysis_layer(self):
        text = (ROOT / "noark5_workflow" / "analysis" / "depot_annotations.py").read_text(encoding="utf-8")
        self.assertIn("annotation_type: str | None", text)
        self.assertIn("username: str | None", text)
        self.assertIn("text_search: str | None", text)
        self.assertNotIn("customtkinter", text)
        self.assertNotIn("tkinter", text)


if __name__ == "__main__":
    unittest.main()
