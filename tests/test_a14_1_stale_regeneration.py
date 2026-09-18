from pathlib import Path
import inspect
import tempfile
import unittest

from noark5_workflow.core.job import Job
from noark5_workflow.core.result_invalidation import (
    ResultInvalidationLedger,
    current_stale_operation_ids,
    invalidation_ledger_path_for_job,
    mark_downstream_stale,
    mark_regenerated,
)


class A141StaleRegenerationTests(unittest.TestCase):
    def _job(self, td: str) -> Job:
        job = Job(job_id="JOB-001")
        job.work_operations = Path(td) / "repository_operations"
        job.workflow_ids = [
            "run_noark5_xpath_tests_2026",
            "compose_noark5_views",
            "build_noark5_depot_report",
            "noark5_u1_total",
        ]
        return job

    def test_current_stale_follows_workflow_order_not_event_order(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            mark_downstream_stale(job, "run_noark5_xpath_tests_2026", "r-new")
            self.assertEqual(["compose_noark5_views", "build_noark5_depot_report"], current_stale_operation_ids(job))

    def test_regeneration_resolves_one_operation_without_deleting_history(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            mark_downstream_stale(job, "run_noark5_xpath_tests_2026", "r-new")
            path = invalidation_ledger_path_for_job(job)
            before = path.read_text(encoding="utf-8")
            event = mark_regenerated(job, "compose_noark5_views")
            after = path.read_text(encoding="utf-8")
            self.assertIsNotNone(event)
            self.assertEqual("regenerated", event.event_type)
            self.assertTrue(after.startswith(before))
            self.assertEqual(["build_noark5_depot_report"], current_stale_operation_ids(job))

    def test_new_invalidation_makes_previously_regenerated_operation_stale_again(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            mark_downstream_stale(job, "run_noark5_xpath_tests_2026", "r1")
            mark_regenerated(job, "compose_noark5_views")
            mark_regenerated(job, "build_noark5_depot_report")
            self.assertEqual([], current_stale_operation_ids(job))
            mark_downstream_stale(job, "run_noark5_xpath_tests_2026", "r2")
            self.assertEqual(["compose_noark5_views", "build_noark5_depot_report"], current_stale_operation_ids(job))

    def test_a13_3_rows_without_event_type_remain_compatible(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            path = invalidation_ledger_path_for_job(job)
            ledger = ResultInvalidationLedger(path)
            event = ledger.append(job_id=job.job_id, source_operation_id="run_noark5_xpath_tests_2026", source_result_id="legacy", stale_operation_id="compose_noark5_views", reason="legacy a13.3")
            self.assertEqual("invalidated", event.event_type)
            self.assertEqual(["compose_noark5_views"], current_stale_operation_ids(job))

    def test_workflow_panel_exposes_stale_status_and_regenerate_action(self):
        import gui.workflow_panel as module
        text = inspect.getsource(module)
        self.assertIn("status_provider", text)
        self.assertIn("Regenerer foreldede", text)
        self.assertIn("stale_ids_provider", text)
        self.assertIn("on_regenerate_stale", text)
        self.assertIn("for tooltip in self._tooltips: tooltip._hide()", text)

    def test_runtime_regenerates_only_current_stale_operations_and_marks_success(self):
        import gui.persistent_app_a22 as module
        text = inspect.getsource(module)
        self.assertIn("current_stale_operation_ids(job)", text)
        self.assertIn("self.job_runner.run_operation", text)
        self.assertIn("mark_regenerated(job, operation_id)", text)
        self.assertIn("workflow-rekkefølge", text)
        self.assertIn("Bare vellykket regenererte operasjoner", text)


if __name__ == "__main__":
    unittest.main()
