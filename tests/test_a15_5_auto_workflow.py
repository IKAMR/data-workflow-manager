
from __future__ import annotations

from pathlib import Path
import unittest

from app.workflow_sequences import (
    noark5_workflow_labels,
    workflow_sequence_by_id,
)

ROOT = Path(__file__).resolve().parents[1]


class A155AutoWorkflowTests(unittest.TestCase):
    def test_standard_sequence_is_canonical_noark5_flow(self):
        sequence = workflow_sequence_by_id("noark5_standard")
        self.assertIsNotNone(sequence)
        self.assertEqual(sequence.profile_id, "noark5")
        self.assertEqual(
            sequence.operation_ids,
            (
                "metadata_inventory",
                "validate_xml_schema",
                "analyse_arkivstruktur",
                "run_noark5_xpath_tests_2026",
                "import_arkade5_reports",
                "compose_noark5_views",
                "build_noark5_depot_report",
            ),
        )

    def test_setup_exposes_none_standard_and_analysis(self):
        labels = noark5_workflow_labels()
        self.assertIn("none", labels)
        self.assertIn("noark5_standard", labels)
        self.assertIn("noark5_analyse", labels)

    def test_discovery_assigns_selected_workflow(self):
        text = (ROOT / "gui" / "jobs_window_a17.py").read_text(encoding="utf-8")
        self.assertIn('settings.get("noark5_discovery_workflow", "noark5_standard")', text)
        self.assertIn("job.set_workflow(workflow_sequence.operation_ids)", text)
        self.assertIn('job.profile_id = "noark5"', text)

    def test_default_setting_is_standard_workflow(self):
        text = (ROOT / "settings.py").read_text(encoding="utf-8")
        self.assertIn('"noark5_discovery_workflow": "noark5_standard"', text)

    def test_settings_exposes_default_noark5_sequence_selector(self):
        text = (ROOT / "gui" / "settings_dialog.py").read_text(encoding="utf-8")
        self.assertIn("Standard workflow for nye Noark 5-jobber", text)
        self.assertIn("noark5_workflow_labels", text)

    def test_new_jobs_auto_apply_default_noark5_sequence(self):
        text = (ROOT / "gui" / "app.py").read_text(encoding="utf-8")
        self.assertIn('configured_sequence(self.settings, profile_id="noark5")', text)
        self.assertIn('job.set_workflow(sequence.operation_ids)', text)


if __name__ == "__main__":
    unittest.main()
