from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from noark5_workflow.core.job import Job, JobStatus
from gui.jobs_window_a18 import A18JobsWindow
from gui.persistent_app_a29 import WorkflowApp


class A163BatchRobustnessTests(unittest.TestCase):
    def _app(self):
        app = object.__new__(WorkflowApp)
        app.settings = {"noark5_discovery_workflow": "noark5_standard"}
        return app

    def test_recoverable_failed_job_is_ready(self):
        job = Job(
            "JOB-001",
            workflow_ids=["one", "two"],
            status=JobStatus.FAILED,
            message="Lagring utilgjengelig - kan fortsette: [Errno 22] Invalid argument",
        )
        self.assertTrue(WorkflowApp._job_is_ready_for_batch(job))
        self.assertTrue(A18JobsWindow._is_ready_to_run(job))

    def test_normal_failed_job_is_not_ready(self):
        job = Job(
            "JOB-001",
            workflow_ids=["one"],
            status=JobStatus.FAILED,
            message="Validering feilet",
        )
        self.assertFalse(WorkflowApp._job_is_ready_for_batch(job))
        self.assertFalse(A18JobsWindow._is_ready_to_run(job))

    def test_io_failure_detection_covers_observed_errno_22(self):
        self.assertTrue(
            WorkflowApp._looks_like_io_failure(
                "[Errno 22] Invalid argument: G:\\repo\\result.json"
            )
        )
        self.assertFalse(
            WorkflowApp._looks_like_io_failure(
                "Faglig valideringsfeil i arkivstruktur.xml"
            )
        )

    def test_storage_preflight_accepts_existing_source_and_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            work = root / "work"
            source.mkdir()
            work.mkdir()
            job = Job(
                "JOB-001",
                source_root=source,
                source_extraction=source,
                work_root=work,
                work_operations=work / "repository_operations" / "_test" / "011",
            )
            app = self._app()
            self.assertEqual([], app._storage_problems(job))

    def test_storage_preflight_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            work.mkdir()
            job = Job(
                "JOB-001",
                source_root=root / "missing-source",
                work_root=work,
            )
            app = self._app()
            problems = app._storage_problems(job)
            self.assertTrue(any("Source er ikke tilgjengelig" in p for p in problems))

    def test_noark5_overview_shows_work_operations_not_generic_output(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "gui"
            / "jobs_window_a18.py"
        ).read_text(encoding="utf-8")
        self.assertIn('text=f"Arbeid: {job.work_operations', text)
        self.assertIn('if job.profile_id == "noark5"', text)

    def test_batch_preflight_has_explicit_empty_workflow_choice(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "gui"
            / "persistent_app_a29.py"
        ).read_text(encoding="utf-8")
        method = text.split("def _batch_preflight", 1)[1].split(
            "# ------------------------------------------------------------------\n    # Recover",
            1,
        )[0]
        self.assertIn("askyesnocancel", method)
        self.assertIn("legg til konfigurert Noark 5-standardworkflow", method)
        self.assertIn("fortsett uten disse jobbene", method)
        self.assertIn("ikke start batchen", method)

    def test_recovery_reuses_existing_execution_cursor(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "gui"
            / "persistent_app_a29.py"
        ).read_text(encoding="utf-8")
        method = text.split("def _execute_job", 1)[1].split(
            "# ------------------------------------------------------------------\n    # Start ready",
            1,
        )[0]
        self.assertIn("job.status = JobStatus.WAITING", method)
        self.assertIn("super()._execute_job", method)
        self.assertIn("next_operation_index + 1", method)


if __name__ == "__main__":
    unittest.main()
