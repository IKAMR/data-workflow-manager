import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.depot_annotations import (
    ANNOTATION_TYPES,
    list_depot_annotations,
    load_depot_annotations,
    record_depot_annotation,
)
from noark5_workflow.core.identity import UserIdentity
from gui.depot_result_views import archive_part_target

ROOT = Path(__file__).resolve().parents[1]


class A6DepotAnnotationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.report = self.root / "depot_validation_report.json"
        self.report.write_text(json.dumps({"report_type": "noark5_depot_validation"}), encoding="utf-8")
        self.user = UserIdentity("u-1", "tester", "Test Bruker", "tester@example.invalid")

    def tearDown(self):
        self.temp.cleanup()

    def test_annotations_are_append_only_and_bound_to_exact_report(self):
        first = record_depot_annotation(
            self.report, annotation_type="note", text="Første merknad", user=self.user,
            view_id="total", target_type="view", target_id="total", target_label="Totaloversikt",
        )
        second = record_depot_annotation(
            self.report, annotation_type="deviation", text="Avvik må følges opp", user=self.user,
            view_id="total", target_type="view", target_id="total", target_label="Totaloversikt",
        )
        store = load_depot_annotations(self.report)
        self.assertEqual(len(store["annotations"]), 2)
        self.assertNotEqual(first["annotation_id"], second["annotation_id"])
        self.report.write_text(json.dumps({"report_type": "noark5_depot_validation", "changed": True}), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_depot_annotations(self.report)

    def test_filters_support_view_and_subview_targets(self):
        record_depot_annotation(
            self.report, annotation_type="note", text="Total", user=self.user,
            view_id="total", target_type="view", target_id="total", target_label="Totaloversikt",
        )
        record_depot_annotation(
            self.report, annotation_type="question", text="Arkivdel", user=self.user,
            view_id="archive_parts", target_type="archive_part", target_id="ap-1", target_label="Sakarkiv",
        )
        rows = list_depot_annotations(
            self.report, view_id="archive_parts", target_type="archive_part", target_id="ap-1"
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["text"], "Arkivdel")

    def test_annotation_types_are_structured_and_cli_neutral(self):
        self.assertIn("note", ANNOTATION_TYPES)
        self.assertIn("deviation", ANNOTATION_TYPES)
        self.assertIn("question", ANNOTATION_TYPES)
        module = (ROOT / "noark5_workflow" / "analysis" / "depot_annotations.py").read_text(encoding="utf-8")
        self.assertNotIn("customtkinter", module)
        self.assertNotIn("tkinter", module)
        self.assertIn("list_depot_annotations", module)

    def test_archive_part_target_prefers_stable_system_id(self):
        target_id, label = archive_part_target(
            {"archive_part": {"system_id": "ap-1", "title": "Sakarkiv"}}, 0
        )
        self.assertEqual(target_id, "ap-1")
        self.assertIn("Sakarkiv", label)

    def test_gui_exposes_comment_actions_and_passes_identity(self):
        views = (ROOT / "gui" / "depot_result_views.py").read_text(encoding="utf-8")
        dialog = (ROOT / "gui" / "depot_assessment_dialog.py").read_text(encoding="utf-8")
        self.assertIn('text="Kommentarer..."', views)
        self.assertIn('text="Kommentarer til arkivdel..."', views)
        self.assertIn("record_depot_annotation", views)
        self.assertIn("user_identity=self.user.as_dict() if self.user else None", dialog)


if __name__ == "__main__":
    unittest.main()
