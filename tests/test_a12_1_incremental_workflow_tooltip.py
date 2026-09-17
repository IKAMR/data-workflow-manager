from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from gui.persistent_app_a21 import WorkflowApp
from noark5_workflow.core.job import Job, JobStatus
from noark5_workflow.core.job_runner import JobContinueError, JobRunner

ROOT = Path(__file__).resolve().parents[1]


class _Registry:
    def __init__(self, ids):
        self.operations = {
            operation_id: SimpleNamespace(
                definition=SimpleNamespace(name=operation_id),
                allow_checkpoint=True,
            )
            for operation_id in ids
        }

    def get(self, operation_id):
        return self.operations[operation_id]


class _Executor:
    def __init__(self):
        self.executed = []

    def execute(self, operation, _ctx):
        self.executed.append(operation.definition.name)
        return SimpleNamespace(ok=True, message="OK", warnings=[], data={})


class A121IncrementalWorkflowAndTooltipTests(unittest.TestCase):
    def test_append_only_extension_contract(self):
        self.assertTrue(
            WorkflowApp._is_append_only_extension(
                ["a", "b"], ["a", "b", "c"],
                old_status=JobStatus.OK, old_cursor=2,
            )
        )

    def test_reorder_is_not_append_only_extension(self):
        self.assertFalse(
            WorkflowApp._is_append_only_extension(
                ["a", "b"], ["b", "a", "c"],
                old_status=JobStatus.OK, old_cursor=2,
            )
        )

    def test_insertion_inside_completed_prefix_is_not_append_only(self):
        self.assertFalse(
            WorkflowApp._is_append_only_extension(
                ["a", "b"], ["a", "x", "b"],
                old_status=JobStatus.OK, old_cursor=2,
            )
        )

    def test_failed_job_is_not_incremental_continue(self):
        self.assertFalse(
            WorkflowApp._is_append_only_extension(
                ["a", "b"], ["a", "b", "c"],
                old_status=JobStatus.FAILED, old_cursor=1,
            )
        )

    def test_ready_partial_cursor_runs_only_appended_tail(self):
        executor = _Executor()
        runner = JobRunner(
            _Registry(["a", "b", "c"]), executor, {},
            source_factory=lambda _root: object(),
        )
        job = Job(job_id="JOB-001", source_root=Path("."), workflow_ids=["a", "b", "c"])
        job.status = JobStatus.READY
        job.next_operation_index = 2
        job.progress = 2 / 3

        outcome = runner.run(job)

        self.assertTrue(outcome.ok)
        self.assertEqual(["c"], executor.executed)
        self.assertEqual(JobStatus.OK, job.status)
        self.assertEqual(3, job.next_operation_index)
        self.assertEqual(1.0, job.progress)

    def test_fresh_ready_job_still_runs_from_operation_one(self):
        executor = _Executor()
        runner = JobRunner(
            _Registry(["a", "b"]), executor, {},
            source_factory=lambda _root: object(),
        )
        job = Job(job_id="JOB-001", source_root=Path("."), workflow_ids=["a", "b"])

        outcome = runner.run(job)

        self.assertTrue(outcome.ok)
        self.assertEqual(["a", "b"], executor.executed)

    def test_checkpoint_continue_contract_remains_strict(self):
        runner = JobRunner(
            _Registry(["a", "b"]), _Executor(), {},
            source_factory=lambda _root: object(),
        )
        job = Job(job_id="JOB-001", source_root=Path("."), workflow_ids=["a", "b"])
        job.status = JobStatus.WAITING
        job.next_operation_index = 1
        with self.assertRaises(JobContinueError):
            runner.continue_job(job)


    def test_append_detection_lives_at_workflow_change_hook_boundary(self):
        text = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        self.assertIn("def _workflow_changed(self, change_kind", text)
        self.assertIn("old_ids = list(job.workflow_ids)", text)
        self.assertIn("new_ids = list(self.workflow.operation_ids())", text)
        self.assertIn('change_kind == "add"', text)
        self.assertIn("super()._workflow_changed(change_kind, operation_id)", text)
        self.assertNotIn("def _add_operation(self, operation_id", text)

    def test_gui_does_not_fake_append_resume_as_checkpoint(self):
        text = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        self.assertIn('self.workflow_panel.set_run_text("Fortsett workflow")', text)
        self.assertNotIn("extension_resume", text)
        self.assertNotIn("job.status = JobStatus.WAITING", text)

    def test_tooltip_watchdog_checks_pointer_and_rearms(self):
        text = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        for token in (
            "TOOLTIP_WATCHDOG_MS",
            "winfo_pointerx",
            "winfo_pointery",
            "winfo_rootx",
            "winfo_rooty",
            "tooltip._hide()",
            "self.after(self.TOOLTIP_WATCHDOG_MS, self._a11_tooltip_watchdog)",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
