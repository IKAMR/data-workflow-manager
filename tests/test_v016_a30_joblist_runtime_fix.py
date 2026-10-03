from __future__ import annotations

from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
