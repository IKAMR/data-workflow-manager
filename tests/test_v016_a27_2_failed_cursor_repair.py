from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class A272FailedCursorRepairContractTests(unittest.TestCase):
    def test_selective_rerun_repairs_failed_cursor_when_same_operation_succeeds(self):
        source = (ROOT / "gui" / "persistent_app_a22.py").read_text(encoding="utf-8")
        self.assertIn("failed_cursor_repair", source)
        self.assertIn("job.mark_operation_completed(position - 1)", source)
        self.assertIn("job.status = JobStatus.READY", source)
        self.assertIn("fortsett fra operasjon", source)
        self.assertIn("self.after(0, self.workflow_panel.refresh)", source)

    def test_other_selective_reruns_still_preserve_cursor(self):
        source = (ROOT / "gui" / "persistent_app_a22.py").read_text(encoding="utf-8")
        self.assertIn("if outcome.ok and failed_cursor_repair:", source)


if __name__ == "__main__":
    unittest.main()
