from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V016A37RuntimeTests(unittest.TestCase):
    def test_version_is_a37(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn('VERSION = "0.1.6-a37"', source)

    def test_a272_delegates_to_a37_runtime(self):
        source = (ROOT / "gui" / "persistent_app_a27_2.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a37_runtime", source)
        self.assertIn("CurrentWorkflowApp()", source)

    def test_a37_builds_on_committed_a36_runtime(self):
        source = (ROOT / "gui" / "persistent_app_a37_runtime.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a36_runtime import WorkflowApp as A36WorkflowApp", source)
        self.assertIn("class WorkflowApp(A36WorkflowApp):", source)

    def test_joblist_has_explicit_noark5_workflow_selector(self):
        source = (ROOT / "gui" / "jobs_window_a35.py").read_text(encoding="utf-8")
        self.assertIn("noark5_workflow_labels", source)
        self.assertIn("CTkOptionMenu", source)
        self.assertIn("Bruk på valgte", source)
        self.assertIn("self.on_apply_workflow(selected, sequence_id)", source)

    def test_standard_arkade_sequence_has_nine_operations(self):
        payload = json.loads(
            (ROOT / "config" / "workflow_sequences.json").read_text(encoding="utf-8")
        )
        sequence = next(
            item for item in payload["sequences"]
            if item["sequence_id"] == "noark5_standard_arkade"
        )
        self.assertEqual(9, len(sequence["operation_ids"]))
        self.assertEqual("arkade5_noark5_test", sequence["operation_ids"][3])
        self.assertEqual("arkade5_pronom_analysis", sequence["operation_ids"][4])

    def test_apply_workflow_targets_all_selected_jobs(self):
        source = (ROOT / "gui" / "persistent_app_a37_runtime.py").read_text(encoding="utf-8")
        self.assertIn("def _a37_apply_workflow(", source)
        self.assertIn("workflow_sequence_by_id(sequence_id", source)
        self.assertIn('job.profile_id = "noark5"', source)
        self.assertIn("job.set_workflow(sequence.operation_ids)", source)
        self.assertNotIn("_bulk_assign_default_noark5_workflow", source)

    def test_joblist_open_job_hides_instead_of_destroying(self):
        source = (ROOT / "gui" / "jobs_window_a35.py").read_text(encoding="utf-8")
        self.assertIn("self.withdraw()", source)
        self.assertNotIn("self.destroy()", source)
        runtime = (ROOT / "gui" / "persistent_app_a37_runtime.py").read_text(encoding="utf-8")
        self.assertIn("self.jobs_window.deiconify()", runtime)

    def test_splitter_code_remains_in_a36_not_reimplemented(self):
        source = (ROOT / "gui" / "persistent_app_a37_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn("left_splitter", source)
        self.assertNotIn("workflow_controls_splitter", source)

    def test_a37_first_run_migrates_batch_default_to_sequential(self):
        source = (ROOT / "gui" / "persistent_app_a37_runtime.py").read_text(encoding="utf-8")
        self.assertIn('"batch_execution_mode"] = "sequential"', source)
        self.assertIn('"batch_max_workers"] = 1', source)
        self.assertIn('a37_safe_sequential_default_applied', source)

    def test_batch_overview_log_is_not_mirrored_to_each_job_work_area(self):
        source = (ROOT / "gui" / "persistent_app_a37_runtime.py").read_text(encoding="utf-8")
        self.assertIn('def _new_run_log(self, run_type: str, planned_jobs: int | None = None):', source)
        self.assertIn('if str(run_type).casefold() != "batch":', source)
        self.assertIn('self.settings[key] = False', source)
        self.assertIn('copy_run_log_to_work_operations', source)



if __name__ == "__main__":
    unittest.main()
