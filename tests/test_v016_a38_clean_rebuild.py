from __future__ import annotations

import unittest
from pathlib import Path

from noark5_workflow.core.work_paths import resolve_dwm_work_root

ROOT = Path(__file__).resolve().parents[1]


class V016A38CleanRebuildTests(unittest.TestCase):
    def test_version_is_a38_or_newer(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn('VERSION = "0.1.6-a39"', source)

    def test_a272_delegates_to_current_runtime(self):
        source = (ROOT / "gui" / "persistent_app_a27_2.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a39_runtime", source)
        self.assertIn("CurrentWorkflowApp()", source)

    def test_a38_builds_only_on_a37(self):
        source = (ROOT / "gui" / "persistent_app_a38_runtime.py").read_text(encoding="utf-8")
        self.assertIn(
            "persistent_app_a37_runtime import WorkflowApp as A37WorkflowApp",
            source,
        )
        self.assertIn("class WorkflowApp(A37WorkflowApp):", source)

    def test_a38_does_not_create_a_second_batch_worker(self):
        source = (ROOT / "gui" / "persistent_app_a38_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn("threading.Thread", source)
        self.assertNotIn("def worker(", source)
        self.assertIn("super()._start_selected_jobs", source)
        self.assertIn("super()._start_ready_jobs", source)
        self.assertIn("super()._start_all_jobs", source)

    def test_a38_supplies_batch_eligibility_used_by_a36_engine(self):
        source = (ROOT / "gui" / "persistent_app_a38_runtime.py").read_text(encoding="utf-8")
        self.assertIn("def _eligible_batch_jobs", source)
        self.assertIn("JobStatus.READY", source)
        self.assertIn("JobStatus.WAITING", source)
        self.assertIn("JobStatus.FAILED", source)

    def test_a38_refreshes_workflow_state_live_during_execution(self):
        source = (ROOT / "gui" / "persistent_app_a38_runtime.py").read_text(encoding="utf-8")
        self.assertIn("def _a38_refresh_execution_ui", source)
        self.assertIn("self.workflow_panel.refresh()", source)
        self.assertIn("state_cb=state", source)
        self.assertIn("_a38_refresh_execution_ui(j)", source)

    def test_a38_removes_periodic_log_heartbeat_from_execute_job(self):
        source = (ROOT / "gui" / "persistent_app_a38_runtime.py").read_text(encoding="utf-8")
        execute = source.split("def _execute_job", 1)[1].split("def _confirm_rerun", 1)[0]
        self.assertNotIn("threading.Event", execute)
        self.assertNotIn("heartbeat_stop", execute)
        self.assertNotIn("threading.Thread", execute)
        self.assertNotIn('f"KJØRER:', execute)
        self.assertIn("self.job_runner.run(", execute)

    def test_confirmation_names_clicked_start_action(self):
        source = (ROOT / "gui" / "persistent_app_a38_runtime.py").read_text(encoding="utf-8")
        self.assertIn('"Start valgte"', source)
        self.assertIn('"Start klare"', source)
        self.assertIn('"Start alle"', source)
        self.assertIn("følgende kjøring er planlagt", source)

    def test_dwm_root_is_idempotent_at_app_root(self):
        path = resolve_dwm_work_root(
            Path("repository_operations") / "dwm",
            settings={"app_work_subfolder": "dwm"},
        )
        self.assertEqual(path, Path("repository_operations") / "dwm")

    def test_dwm_root_is_idempotent_one_job_rule_below_app_root(self):
        path = resolve_dwm_work_root(
            Path("repository_operations") / "dwm" / "a01",
            settings={"app_work_subfolder": "dwm"},
        )
        self.assertEqual(path, Path("repository_operations") / "dwm" / "a01")

    def test_dwm_root_is_added_to_unresolved_base(self):
        path = resolve_dwm_work_root(
            Path("repository_operations"),
            settings={"app_work_subfolder": "dwm"},
        )
        self.assertEqual(path, Path("repository_operations") / "dwm")

    def test_unrelated_ancestor_named_dwm_does_not_suppress_app_root(self):
        path = resolve_dwm_work_root(
            Path("dwm") / "client" / "repository_operations",
            settings={"app_work_subfolder": "dwm"},
        )
        self.assertEqual(
            path,
            Path("dwm") / "client" / "repository_operations" / "dwm",
        )

    def test_interrupted_skipped_jobs_are_made_runnable_without_resetting_cursor(self):
        source = (ROOT / "gui" / "persistent_app_a38_runtime.py").read_text(encoding="utf-8")
        self.assertIn("job.status == JobStatus.SKIPPED", source)
        self.assertIn("job.status = JobStatus.READY", source)
        eligible = source.split("def _eligible_batch_jobs", 1)[1].split("def _start_selected_jobs", 1)[0]
        self.assertNotIn("job.reset_execution(", eligible)

    def test_a38_jobs_window_keeps_open_enabled_during_batch(self):
        source = (ROOT / "gui" / "jobs_window_a38.py").read_text(encoding="utf-8")
        self.assertIn('view["open"].configure(state="normal")', source)
        runtime = (ROOT / "gui" / "persistent_app_a38_runtime.py").read_text(encoding="utf-8")
        self.assertIn("A38JobsWindow", runtime)

    def test_finished_jobs_are_unchecked_by_default(self):
        source = (ROOT / "gui" / "jobs_window_a38.py").read_text(encoding="utf-8")
        self.assertIn("job.status != JobStatus.OK", source)

    def test_streaming_xsd_validation_accepts_cancel_callback(self):
        source = (ROOT / "noark5_workflow" / "analysis" / "xml_schema_validation.py").read_text(encoding="utf-8")
        self.assertIn("cancelled_cb", source)
        self.assertIn("XmlSchemaValidationCancelled", source)
        op = (ROOT / "noark5_workflow" / "operations" / "validate_xml_schema.py").read_text(encoding="utf-8")
        self.assertIn("cancelled_cb=ctx.cancelled", op)
        self.assertIn('"XML/XSD-validering avbrutt av bruker."', op)


if __name__ == "__main__":
    unittest.main()
