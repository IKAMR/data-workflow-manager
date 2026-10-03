from __future__ import annotations

from pathlib import Path
import unittest
from types import SimpleNamespace

from gui.app import WorkflowApp

ROOT = Path(__file__).resolve().parents[1]


class A30JoblistRuntimeFixTests(unittest.TestCase):
    def test_jobs_window_allows_open_during_running_batch(self):
        text = (ROOT / "gui" / "jobs_window.py").read_text(encoding="utf-8")
        self.assertIn("self.on_open_job(job)", text)
        self.assertIn("if not self._batch_running:", text)
        self.assertIn('text="Åpne"', text)

    def test_jobs_window_is_not_modal_and_is_resizable(self):
        text = (ROOT / "gui" / "jobs_window.py").read_text(encoding="utf-8")
        self.assertIn("self.resizable(True, True)", text)
        self.assertNotIn("self.transient(master)", text)

    def test_left_split_height_is_persisted_and_stable(self):
        class DummyLeft:
            def __init__(self):
                self.rows = {}
            def winfo_exists(self):
                return True
            def winfo_height(self):
                return 820
            def grid_rowconfigure(self, row, **kwargs):
                self.rows[row] = kwargs
            def configure(self, **kwargs):
                self.config = kwargs

        app = object.__new__(WorkflowApp)
        app.left = DummyLeft()
        app.source_panel = type("SourcePanel", (), {"configure": lambda self, **kwargs: None})()
        app.settings = {"left_source_height": 170}
        app._left_source_height = 170
        self.assertEqual(app._coerce_left_source_height(120), 120)
        self.assertEqual(app._coerce_left_source_height(1000), 640)
        app._left_source_height = 120
        app._apply_left_source_height()
        self.assertEqual(app._left_source_height, 120)

    def test_app_follows_the_running_job_after_batch_progress(self):
        text = (ROOT / "gui" / "app.py").read_text(encoding="utf-8")
        self.assertIn("self.current_job = job", text)
        self.assertIn("self._show_job_log(job)", text)
        self.assertIn("self.jobs_window.schedule_refresh", text)

    def test_left_split_uses_runtime_state_not_stale_settings_default(self):
        class DummyLeft:
            def __init__(self):
                self.rows = {}
            def winfo_exists(self):
                return True
            def winfo_height(self):
                return 820
            def grid_rowconfigure(self, row, **kwargs):
                self.rows[row] = kwargs
            def configure(self, **kwargs):
                self.config = kwargs

        app = object.__new__(WorkflowApp)
        app.left = DummyLeft()
        app.settings = {"left_source_height": 170}
        app.source_panel = type("SourcePanel", (), {"configure": lambda self, **kwargs: None})()
        app._left_source_height = 220
        app._sync_left_split_after_resize()
        self.assertEqual(app._left_source_height, 220)

    def test_bottom_splitter_supports_persisted_height(self):
        app = object.__new__(WorkflowApp)
        app.settings = {"bottom_panel_height": 240}
        app._bottom_panel_height = 240
        self.assertEqual(app._coerce_bottom_panel_height(300), 300)
        app._bottom_panel_height = 120
        self.assertEqual(app._coerce_bottom_panel_height(120), 120)

    def test_app_opens_joblist_in_front_of_main_window(self):
        text = (ROOT / "gui" / "app.py").read_text(encoding="utf-8")
        self.assertIn("self.jobs_window.lift()", text)
        self.assertIn("self.jobs_window.focus_force()", text)

    def test_output_subfolder_rule_materializes_effective_work_path(self):
        job = SimpleNamespace(
            job_id="JOB-003",
            name="Test",
            active_extraction_root=Path("source"),
            work_operations=Path("C:/repo/repository_operations"),
        )

        class DummyJobs:
            output_subfolder_rule = "<jobno>"

            def jobs(self):
                return [job]

        app = type(
            "DummyApp",
            (),
            {
                "settings": {"app_work_subfolder": "dwm"},
                "jobs": DummyJobs(),
                "_job_position": lambda self, _job: 1,
                "_get_app_work_subfolder": lambda self: "dwm",
            },
        )()
        WorkflowApp._apply_effective_work_operations(app, job)

        self.assertEqual(
            job._effective_work_operations,
            Path("C:/repo/repository_operations") / "dwm" / "003",
        )


if __name__ == "__main__":
    unittest.main()
