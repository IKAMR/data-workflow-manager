from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from noark5_workflow.core.job import JobStatus


ROOT = Path(__file__).resolve().parents[1]


class A16482JobProgressTests(unittest.TestCase):
    @staticmethod
    def _formatter_source():
        # Importing the GUI module is safe in the existing suite, but these
        # contract tests also ensure the intended visible wording remains.
        from gui.jobs_window_a20 import A20JobsWindow
        return A20JobsWindow

    def test_running_xpath_shows_operation_test_and_percent(self):
        cls = self._formatter_source()
        job = SimpleNamespace(
            status=JobStatus.RUNNING,
            workflow_ids=["a", "b", "c", "xpath", "views", "report"],
            next_operation_index=3,
            progress=0.55,
            log_entries=[
                "[JOB-001] TEST START 23/57 | kdrs.c22",
                "[JOB-001] TEST SLUTT 23/57 | kdrs.c22 | ok",
                "[JOB-001] TEST START 24/57 | kdrs.c23",
            ],
        )
        self.assertEqual(
            cls._progress_text(job),
            "Operasjon 4/6 · Test 24/57 · 55%",
        )

    def test_running_non_test_operation_omits_test_segment(self):
        cls = self._formatter_source()
        job = SimpleNamespace(
            status=JobStatus.RUNNING,
            workflow_ids=["a", "b", "c", "d", "e", "f"],
            next_operation_index=1,
            progress=0.25,
            log_entries=["START: Valider XML"],
        )
        self.assertEqual(
            cls._progress_text(job),
            "Operasjon 2/6 · 25%",
        )

    def test_non_running_job_keeps_compact_percent(self):
        cls = self._formatter_source()
        job = SimpleNamespace(
            status=JobStatus.READY,
            workflow_ids=["a", "b"],
            next_operation_index=0,
            progress=0.0,
            log_entries=[],
        )
        self.assertEqual(cls._progress_text(job), "0%")

    def test_job_row_uses_expanded_progress_width_while_running(self):
        source = (ROOT / "gui" / "jobs_window_a20.py").read_text(encoding="utf-8")
        self.assertIn('text=self._progress_text(job)', source)
        self.assertIn('width=250 if job.status == JobStatus.RUNNING else 70', source)


if __name__ == "__main__":
    unittest.main()
