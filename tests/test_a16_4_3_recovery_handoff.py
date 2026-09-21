from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from noark5_workflow.core.job import Job, JobStatus
from gui.persistent_app_a31 import WorkflowApp


class A1643RecoveryHandoffTests(unittest.TestCase):
    def _app(self):
        app = object.__new__(WorkflowApp)
        return app

    def test_preflight_accepts_source_root_if_extraction_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            work.mkdir()
            job = Job(
                "JOB-004",
                source_root=root,
                source_extraction=root / "missing" / "content",
                work_root=work,
            )
            app = self._app()
            self.assertEqual([], app._storage_problems(job))

    def test_preflight_rejects_when_both_source_paths_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            work = base / "work"
            work.mkdir()
            job = Job(
                "JOB-004",
                source_root=base / "missing-root",
                source_extraction=base / "missing-root" / "content",
                work_root=work,
            )
            app = self._app()
            problems = app._storage_problems(job)
            self.assertTrue(any("Source er ikke tilgjengelig" in p for p in problems))

    def test_runtime_bypasses_a29_recovery_wrapper(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "gui"
            / "persistent_app_a31.py"
        ).read_text(encoding="utf-8")
        method = text.split("def _execute_job", 1)[1].split("def run_gui", 1)[0]
        self.assertIn("job.status = JobStatus.WAITING", method)
        self.assertIn("A28WorkflowApp._execute_job(", method)
        self.assertNotIn("super()._execute_job(job, batch_mode=batch_mode)", method.split(
            "if not self._recoverable_storage_failure(job):",1
        )[1].split("# Preserve absolutely",1)[1])

    def test_recovery_contract_preserves_operation_params(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "gui"
            / "persistent_app_a31.py"
        ).read_text(encoding="utf-8")
        self.assertIn("params_before = dict(job.operation_params or {})", text)
        self.assertIn("job.operation_params = params_before", text)
        self.assertIn("cursor = int(job.next_operation_index or 0)", text)


if __name__ == "__main__":
    unittest.main()
