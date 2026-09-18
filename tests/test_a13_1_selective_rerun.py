from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from noark5_workflow.core.job import Job, JobStatus
from noark5_workflow.core.job_runner import JobRunner
from noark5_workflow.core.result import OperationResult


class _Operation:
    raw_result_record = False

    def __init__(self, operation_id: str):
        self.definition = SimpleNamespace(operation_id=operation_id, name=f"Operation {operation_id}")

    def can_run(self, _ctx):
        return True, ""

    def run(self, _ctx):
        return OperationResult(True, "ok", data={"value": 1})


class _Registry:
    def __init__(self):
        self.items = {"a": _Operation("a"), "b": _Operation("b"), "c": _Operation("c")}

    def get(self, operation_id):
        return self.items[operation_id]


class _Executor:
    def __init__(self):
        self.executed = []

    def execute(self, operation, _ctx):
        self.executed.append(operation.definition.operation_id)
        return operation.run(_ctx)


class SelectiveRerunTests(unittest.TestCase):
    def test_runs_only_selected_operation_and_preserves_job_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executor = _Executor()
            runner = JobRunner(_Registry(), executor, {}, source_factory=lambda _root: object())
            job = Job(
                "JOB-001",
                source_root=root,
                workflow_ids=["a", "b", "c"],
                status=JobStatus.OK,
                progress=1.0,
                next_operation_index=3,
                message="Workflow fullført",
            )
            outcome = runner.run_operation(job, "b")
            self.assertTrue(outcome.ok)
            self.assertEqual(executor.executed, ["b"])
            self.assertEqual(job.status, JobStatus.OK)
            self.assertEqual(job.progress, 1.0)
            self.assertEqual(job.next_operation_index, 3)
            self.assertEqual(job.message, "Workflow fullført")

    def test_identity_is_operation_id_not_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executor = _Executor()
            runner = JobRunner(_Registry(), executor, {}, source_factory=lambda _root: object())
            job = Job("JOB-001", source_root=root, workflow_ids=["c", "a", "b"])
            runner.run_operation(job, "b")
            self.assertEqual(executor.executed, ["b"])

    def test_rejects_operation_not_in_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = JobRunner(_Registry(), _Executor(), {}, source_factory=lambda _root: object())
            job = Job("JOB-001", source_root=root, workflow_ids=["a"])
            with self.assertRaises(ValueError):
                runner.run_operation(job, "b")

    def test_gui_layer_wires_selective_rerun_callback(self):
        text = (Path(__file__).resolve().parents[1] / "gui" / "persistent_app_a22.py").read_text(encoding="utf-8")
        self.assertIn("self.workflow_panel.on_rerun = self._rerun_selected_operation", text)
        self.assertIn("self.job_runner.run_operation", text)

    def test_workflow_panel_uses_stable_operation_id_callback(self):
        text = (Path(__file__).resolve().parents[1] / "gui" / "workflow_panel.py").read_text(encoding="utf-8")
        self.assertIn("command=lambda oid=op_id: self.on_rerun(oid)", text)
        self.assertIn("Kjør bare denne operasjonen på nytt", text)


if __name__ == "__main__":
    unittest.main()
