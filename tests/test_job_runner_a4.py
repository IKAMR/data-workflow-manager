import unittest
from pathlib import Path

from noark5_workflow.core.job import Job, JobStatus
from noark5_workflow.core.job_runner import JobRunner
from noark5_workflow.core.operation import BaseOperation, OperationDefinition
from noark5_workflow.core.result import OperationResult


class FakeRegistry:
    def __init__(self, operations):
        self.operations = {op.definition.operation_id: op for op in operations}

    def get(self, operation_id):
        return self.operations[operation_id]


class FakeExecutor:
    def execute(self, operation, ctx):
        return operation.run(ctx)


class FakeOperation(BaseOperation):
    def __init__(self, operation_id, *, ok=True):
        self.definition = OperationDefinition(operation_id, operation_id.upper(), "test")
        self.ok = ok
        self.calls = 0
        self.params = {}

    def configure(self, params):
        self.params = dict(params)

    def run(self, ctx):
        self.calls += 1
        return OperationResult(self.ok, f"{self.definition.operation_id} result")


class JobRunnerA4Tests(unittest.TestCase):
    def make_runner(self, *operations):
        return JobRunner(
            FakeRegistry(operations),
            FakeExecutor(),
            {},
            source_factory=lambda path: object(),
        )

    def test_successful_job_runs_without_gui(self):
        a = FakeOperation("a")
        b = FakeOperation("b")
        job = Job("JOB-001", Path("source"), workflow_ids=["a", "b"])
        outcome = self.make_runner(a, b).run(job)
        self.assertTrue(outcome.ok)
        self.assertTrue(outcome.persist_recommended)
        self.assertEqual(job.status, JobStatus.OK)
        self.assertEqual(job.next_operation_index, 2)
        self.assertEqual(job.progress, 1.0)
        self.assertEqual((a.calls, b.calls), (1, 1))

    def test_checkpoint_stops_and_resume_continues(self):
        a = FakeOperation("a")
        b = FakeOperation("b")
        job = Job(
            "JOB-001",
            Path("source"),
            workflow_ids=["a", "b"],
            checkpoint_after=["a"],
        )
        runner = self.make_runner(a, b)
        first = runner.run(job)
        self.assertTrue(first.ok)
        self.assertEqual(job.status, JobStatus.WAITING)
        self.assertEqual(job.next_operation_index, 1)
        self.assertEqual((a.calls, b.calls), (1, 0))

        second = runner.run(job)
        self.assertTrue(second.ok)
        self.assertEqual(job.status, JobStatus.OK)
        self.assertEqual(job.next_operation_index, 2)
        self.assertEqual((a.calls, b.calls), (1, 1))

    def test_failure_keeps_cursor_on_failed_operation(self):
        a = FakeOperation("a")
        b = FakeOperation("b", ok=False)
        job = Job("JOB-001", Path("source"), workflow_ids=["a", "b"])
        outcome = self.make_runner(a, b).run(job)
        self.assertFalse(outcome.ok)
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertEqual(job.next_operation_index, 1)
        self.assertEqual((a.calls, b.calls), (1, 1))

    def test_cancel_before_first_operation(self):
        a = FakeOperation("a")
        job = Job("JOB-001", Path("source"), workflow_ids=["a"])
        outcome = self.make_runner(a).run(job, cancelled_cb=lambda: True)
        self.assertFalse(outcome.ok)
        self.assertFalse(outcome.persist_recommended)
        self.assertEqual(job.status, JobStatus.INTERRUPTED)
        self.assertEqual(a.calls, 0)


if __name__ == "__main__":
    unittest.main()
