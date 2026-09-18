from pathlib import Path
import tempfile
import unittest

from noark5_workflow.core.job import Job, JobStatus
from gui.workflow_status import STATUS_SPECS, operation_status_key

ROOT = Path(__file__).resolve().parents[1]
PANEL = (ROOT / "gui" / "workflow_panel.py").read_text(encoding="utf-8")
INFO = (ROOT / "gui" / "info_panel.py").read_text(encoding="utf-8")
RUNTIME = (ROOT / "gui" / "persistent_app_a22.py").read_text(encoding="utf-8")
DOC = ROOT / "docs" / "WORKFLOW_STATUS_AND_INFO_PANEL.md"
IMAGE = ROOT / "docs" / "images" / "workflow-status-info-panel-a14.3.png"


class A143StatusInfoPanelTests(unittest.TestCase):
    def test_stale_is_orange_and_failure_is_red(self):
        self.assertEqual("#f6b91a", STATUS_SPECS["stale"].color)
        self.assertEqual("#ff4d4f", STATUS_SPECS["failed"].color)
        self.assertNotEqual(STATUS_SPECS["stale"].color, STATUS_SPECS["failed"].color)

    def test_stale_overrides_completed_status(self):
        job = Job(job_id="JOB-001", workflow_ids=["op1"])
        job.status = JobStatus.OK
        job.next_operation_index = 1
        self.assertEqual("ok", operation_status_key(job, "op1", set()))
        self.assertEqual("stale", operation_status_key(job, "op1", {"op1"}))

    def test_failed_cursor_is_red_status_and_completed_prefix_is_ok(self):
        job = Job(job_id="JOB-001", workflow_ids=["op1", "op2"])
        job.status = JobStatus.FAILED
        job.next_operation_index = 1
        self.assertEqual("ok", operation_status_key(job, "op1", set()))
        self.assertEqual("failed", operation_status_key(job, "op2", set()))

    def test_panel_uses_status_icon_tooltip_and_no_inline_foreldet_text(self):
        self.assertIn("status_provider", PANEL)
        self.assertIn("status_spec(status_key)", PANEL)
        self.assertIn("self._add_tooltip(status_icon", PANEL)
        self.assertNotIn('[FORELDET]', PANEL)

    def test_info_panel_is_collapsible_with_f9_and_remembers_visibility(self):
        self.assertIn('values=["Statusikoner", "Hjelp", "Om"]', INFO)
        self.assertIn('self.bind("<F9>"', RUNTIME)
        self.assertIn('info_panel_visible', RUNTIME)
        self.assertIn('grid_remove()', RUNTIME)
        self.assertIn('InfoPanel(self, on_close=self._hide_info_panel)', RUNTIME)

    def test_documentation_and_reference_image_are_in_repository_delta(self):
        self.assertTrue(DOC.is_file())
        self.assertTrue(IMAGE.is_file())
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("Foreldet", text)
        self.assertIn("oransje", text)
        self.assertIn("Feil", text)
        self.assertIn("rød", text)
        self.assertIn("F9", text)


if __name__ == "__main__":
    unittest.main()
