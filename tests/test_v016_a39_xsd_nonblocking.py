from __future__ import annotations

import unittest
from pathlib import Path

from noark5_workflow.core.job import Job, JobStatus
from noark5_workflow.core.job_runner_a39 import A39JobRunner
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
    def __init__(self, operation_id, result):
        self.definition = OperationDefinition(operation_id, operation_id, "test")
        self.result = result
        self.calls = 0

    def run(self, ctx):
        self.calls += 1
        return self.result


class V016A39XsdNonBlockingTests(unittest.TestCase):
    def make_runner(self, *operations):
        return A39JobRunner(
            FakeRegistry(operations),
            FakeExecutor(),
            {},
            source_factory=lambda path: object(),
        )

    def test_xsd_validation_finding_continues_to_next_operation(self):
        xsd = FakeOperation(
            "validate_xml_schema",
            OperationResult(
                False,
                "XML/XSD-validering feilet med 2 avvik. Rapport: report.json",
                data={"valid": False, "errors": [{"message": "x"}, {"message": "y"}]},
            ),
        )
        analyse = FakeOperation(
            "analyze_archive_structure",
            OperationResult(True, "Analyse fullført"),
        )
        job = Job(
            "JOB-002",
            Path("."),
            workflow_ids=["validate_xml_schema", "analyze_archive_structure"],
        )
        logs = []

        outcome = self.make_runner(xsd, analyse).run(job, log_cb=logs.append)

        self.assertTrue(outcome.ok)
        self.assertEqual(job.status, JobStatus.OK)
        self.assertEqual(job.next_operation_index, 2)
        self.assertEqual((xsd.calls, analyse.calls), (1, 1))
        self.assertEqual(job.message, "Workflow fullført med XSD-avvik")
        self.assertTrue(any("AVVIK:" in line for line in logs))

    def test_technical_xsd_failure_still_blocks_workflow(self):
        xsd = FakeOperation(
            "validate_xml_schema",
            OperationResult(
                False,
                "Kunne ikke avgjøre hvilken lokal XSD som hører til arkivstruktur.xml.",
            ),
        )
        analyse = FakeOperation(
            "analyze_archive_structure",
            OperationResult(True, "Analyse fullført"),
        )
        job = Job(
            "JOB-002",
            Path("."),
            workflow_ids=["validate_xml_schema", "analyze_archive_structure"],
        )

        outcome = self.make_runner(xsd, analyse).run(job)

        self.assertFalse(outcome.ok)
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertEqual(job.next_operation_index, 0)
        self.assertEqual((xsd.calls, analyse.calls), (1, 0))

    def test_a39_runtime_builds_on_a38_and_installs_a39_runner(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "gui" / "persistent_app_a39_runtime.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a38_runtime import WorkflowApp as A38WorkflowApp", source)
        self.assertIn("class WorkflowApp(A38WorkflowApp):", source)
        self.assertIn("self.job_runner = A39JobRunner(", source)

    def test_historical_entry_point_delegates_to_a39(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "gui" / "persistent_app_a27_2.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a39_runtime", source)

    def test_version_is_a39(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "version.py").read_text(encoding="utf-8")
        self.assertIn('VERSION = "0.1.6-a39"', source)


if __name__ == "__main__":
    unittest.main()
