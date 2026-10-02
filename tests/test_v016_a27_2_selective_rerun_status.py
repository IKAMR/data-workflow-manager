from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from noark5_workflow.core.job import Job, JobStatus
from gui.workflow_status import operation_status_key


class A272SelectiveRerunStatusTests(unittest.TestCase):
    def test_failed_cursor_stays_failed_without_new_result(self):
        job = Job(
            "JOB-001",
            source_root=Path("."),
            workflow_ids=["a", "b"],
            status=JobStatus.FAILED,
            next_operation_index=0,
        )
        with patch("gui.workflow_status.operation_results", return_value=[]):
            self.assertEqual(operation_status_key(job, "a"), "failed")

    def test_successful_selective_rerun_overrides_old_failed_cursor_icon(self):
        job = Job(
            "JOB-001",
            source_root=Path("."),
            workflow_ids=["a", "b"],
            status=JobStatus.FAILED,
            next_operation_index=0,
        )
        results = [
            SimpleNamespace(ok=False),
            SimpleNamespace(ok=True),
        ]
        with patch("gui.workflow_status.operation_results", return_value=results):
            self.assertEqual(operation_status_key(job, "a"), "ok")

    def test_latest_failed_selective_rerun_remains_failed(self):
        job = Job(
            "JOB-001",
            source_root=Path("."),
            workflow_ids=["a", "b"],
            status=JobStatus.FAILED,
            next_operation_index=0,
        )
        results = [
            SimpleNamespace(ok=True),
            SimpleNamespace(ok=False),
        ]
        with patch("gui.workflow_status.operation_results", return_value=results):
            self.assertEqual(operation_status_key(job, "a"), "failed")

    def test_runtime_refreshes_workflow_panel_after_selective_rerun(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "gui" / "persistent_app_a22.py").read_text(encoding="utf-8")
        self.assertIn("self.after(0, self.workflow_panel.refresh)", source)


if __name__ == "__main__":
    unittest.main()
