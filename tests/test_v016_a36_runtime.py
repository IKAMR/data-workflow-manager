from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V016A36RuntimeTests(unittest.TestCase):
    def test_a272_delegates_to_current_runtime_after_a37(self):
        source = (ROOT / "gui" / "persistent_app_a27_2.py").read_text(encoding="utf-8")
        match = re.search(
            r"from \.persistent_app_a(\d+)_runtime import WorkflowApp as CurrentWorkflowApp",
            source,
        )
        self.assertIsNotNone(match, source)
        self.assertGreaterEqual(int(match.group(1)), 37)
        self.assertIn("CurrentWorkflowApp()", source)

    def test_runtime_extends_complete_a272_feature_chain(self):
        source = (ROOT / "gui" / "persistent_app_a36_runtime.py").read_text(encoding="utf-8")
        self.assertIn("from .persistent_app_a27_2 import WorkflowApp as A27_2WorkflowApp", source)
        self.assertIn("class WorkflowApp(A27_2WorkflowApp):", source)
        self.assertNotIn("class WorkflowApp(A35WorkflowApp):", source)
        self.assertNotIn("class WorkflowApp(A71WorkflowApp):", source)

    def test_joblist_callbacks_are_provided_by_a272_chain(self):
        runtime = (ROOT / "gui" / "persistent_app_a36_runtime.py").read_text(encoding="utf-8")
        callback_sources = {
            "_a242_apply_discovery": ROOT / "gui" / "persistent_app_a24_3.py",
            "_a246_fill_storage_suggestions": ROOT / "gui" / "persistent_app_a25_3.py",
            "_a251_discover_arkade5_results": ROOT / "gui" / "persistent_app_a25_6.py",
            "_a266_open_arkade5_run": ROOT / "gui" / "persistent_app_a26_6.py",
        }
        for callback, path in callback_sources.items():
            self.assertIn(f"def {callback}", path.read_text(encoding="utf-8"), callback)
        self.assertIn("on_extraction_discovery=self._a242_apply_discovery", runtime)
        self.assertIn("on_fill_storage_suggestions=self._a246_fill_storage_suggestions", runtime)
        self.assertIn("on_discover_arkade5_results=self._a251_discover_arkade5_results", runtime)
        self.assertIn("on_run_arkade5=self._a266_open_arkade5_run", runtime)

    def test_jobs_window_has_visible_selection_and_bulk_standard(self):
        source = (ROOT / "gui" / "jobs_window_a34.py").read_text(encoding="utf-8")
        self.assertIn("CTkCheckBox", source)
        self.assertIn("Standard valgte", source)
        self.assertIn("Standard tomme", source)
        self.assertIn('view["card"].grid_configure(row=index)', source)

    def test_runtime_uses_jobrunner_and_persists_state(self):
        source = (ROOT / "gui" / "persistent_app_a36_runtime.py").read_text(encoding="utf-8")
        self.assertIn("self.job_runner.run(", source)
        self.assertIn("save_job_list(", source)
        self.assertNotIn("self.executor.execute(operation", source)

    def test_external_cli_can_be_cancelled(self):
        cli = (ROOT / "noark5_workflow" / "external_tools" / "cli_runner.py").read_text(encoding="utf-8")
        operation = (ROOT / "noark5_workflow" / "operations" / "run_arkade5_cli.py").read_text(encoding="utf-8")
        self.assertIn("cancelled_cb", cli)
        self.assertIn("process.terminate()", cli)
        self.assertIn("cancelled_cb=ctx.cancelled", operation)

    def test_left_splitters_are_continuous_and_capture_drag(self):
        source = (ROOT / "gui" / "persistent_app_a36_runtime.py").read_text(encoding="utf-8")
        self.assertIn("import tkinter as tk", source)
        self.assertIn("self.left_splitter = tk.Frame(", source)
        self.assertIn("self.workflow_controls_splitter = tk.Frame(", source)
        self.assertIn("left_workflow_split_y", source)
        self.assertNotIn("workflow_controls_collapsed", source)
        self.assertIn("self.left_splitter.grab_set()", source)
        self.assertIn("self.left_splitter.grab_release()", source)
        self.assertIn("self.workflow_controls_splitter.grab_set()", source)
        self.assertIn("self.workflow_controls_splitter.grab_release()", source)
        self.assertIn('self.left_splitter.bind("<B1-Motion>"', source)
        self.assertIn('"<B1-Motion>", self._drag_workflow_controls', source)
        self.assertNotIn('self.left.bind("<Configure>"', source)

    def test_joblist_uses_complete_runtime_chain_and_single_open_path(self):
        source = (ROOT / "gui" / "persistent_app_a36_runtime.py").read_text(encoding="utf-8")
        self.assertIn("class WorkflowApp(A27_2WorkflowApp):", source)
        self.assertIn("self.jobs_window = A34JobsWindow(", source)
        self.assertIn("self.jobs_window.lift()", source)
        self.assertIn("self.jobs_window.focus_force()", source)
        self.assertNotIn("def _a36_present_jobs_window", source)
        self.assertNotIn("window.transient(self)", source)

    def test_start_selected_callback_exists_and_uses_joblist_selection(self):
        source = (ROOT / "gui" / "persistent_app_a36_runtime.py").read_text(encoding="utf-8")
        self.assertIn("def _start_selected_jobs(self) -> None:", source)
        self.assertIn("self.jobs_window._selected_jobs_for_run()", source)
        self.assertIn("self._start_batch_jobs(selected)", source)

    def test_left_splitters_persist_independent_positions(self):
        source = (ROOT / "gui" / "persistent_app_a36_runtime.py").read_text(encoding="utf-8")
        self.assertIn('"left_source_height"', source)
        self.assertIn('"left_workflow_split_y"', source)
        self.assertIn("self._a36_apply_workflow_split_y()", source)
        self.assertNotIn('"workflow_items_height"', source)


if __name__ == "__main__":
    unittest.main()
