from pathlib import Path
import tempfile
import unittest

from noark5_workflow.core.job import Job
from noark5_workflow.core.result_invalidation import (
    ResultInvalidationLedger,
    downstream_operation_ids,
    invalidation_ledger_path_for_job,
    mark_downstream_stale,
)


class A133DownstreamInvalidationTests(unittest.TestCase):
    def _job(self, td: str) -> Job:
        job = Job(job_id="JOB-001")
        job.work_operations = Path(td) / "repository_operations"
        job.workflow_ids = [
            "validate_noark5_xsd",
            "run_noark5_xpath_tests_2026",
            "compose_noark5_views",
            "build_noark5_depot_report",
            "noark5_u1_total",
        ]
        return job

    def test_dependencies_are_semantic_not_position_based(self):
        self.assertEqual(
            ["compose_noark5_views", "build_noark5_depot_report"],
            downstream_operation_ids("run_noark5_xpath_tests_2026"),
        )

    def test_xpath_current_change_marks_views_and_report_stale(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            stale = mark_downstream_stale(job, "run_noark5_xpath_tests_2026", "r-new")
            self.assertEqual(["compose_noark5_views", "build_noark5_depot_report"], stale)
            events = ResultInvalidationLedger(invalidation_ledger_path_for_job(job)).events()
            self.assertEqual(2, len(events))
            self.assertEqual("r-new", events[0].source_result_id)

    def test_reference_operation_is_not_invalidated_just_because_it_is_later(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            stale = mark_downstream_stale(job, "run_noark5_xpath_tests_2026", "r-new")
            self.assertNotIn("noark5_u1_total", stale)

    def test_only_operations_present_in_job_are_marked(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            job.workflow_ids.remove("build_noark5_depot_report")
            stale = mark_downstream_stale(job, "run_noark5_xpath_tests_2026", "r-new")
            self.assertEqual(["compose_noark5_views"], stale)

    def test_invalidation_ledger_is_append_only(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            mark_downstream_stale(job, "run_noark5_xpath_tests_2026", "r1")
            path = invalidation_ledger_path_for_job(job)
            first = path.read_text(encoding="utf-8")
            mark_downstream_stale(job, "run_noark5_xpath_tests_2026", "r2")
            second = path.read_text(encoding="utf-8")
            self.assertTrue(second.startswith(first))
            self.assertEqual(4, len(ResultInvalidationLedger(path).events()))


if __name__ == "__main__":
    unittest.main()
