from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A159WorkflowStatusProgressTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (
            ROOT / "gui" / "persistent_app_a26.py"
        ).read_text(encoding="utf-8")
        self.main = (
            ROOT / "main.py"
        ).read_text(encoding="utf-8")

    def test_current_runtime_is_preserved_in_chain(self):
        self.assertIn(
            "from gui.persistent_app_a26 import WorkflowApp as _A26WorkflowApp",
            self.main,
        )
        self.assertIn(
            "from gui.persistent_app_a27 import run_gui",
            self.main,
        )

    def test_status_provider_is_explicitly_wired(self):
        self.assertIn(
            "self.workflow_panel.status_provider = self._a159_operation_status_key",
            self.runtime,
        )
        self.assertIn("operation_status_key(", self.runtime)

    def test_runner_state_refreshes_active_workflow_icons(self):
        method = self.runtime.split(
            "def _runner_state_changed(self, job) -> None:", 1
        )[1].split("def _execute_job", 1)[0]
        self.assertIn("super()._runner_state_changed(job)", method)
        self.assertIn("_refresh_active_workflow_status", method)

    def test_final_job_state_refreshes_icons(self):
        method = self.runtime.split(
            "def _execute_job(self, job, *, batch_mode: bool) -> bool:", 1
        )[1].split("def _progress_callback_for_job", 1)[0]
        self.assertIn("super()._execute_job", method)
        self.assertGreaterEqual(
            method.count("_refresh_active_workflow_status"),
            2,
        )

    def test_progress_has_operation_position_and_inner_detail(self):
        method = self.runtime.split(
            "def _progress_callback_for_job", 1
        )[1]
        self.assertIn("Operasjon {operation_number}/{total}", method)
        self.assertIn("detail", method)
        self.assertIn("super()._progress_callback_for_job", method)

    def test_progress_updates_tk_on_gui_thread(self):
        method = self.runtime.split(
            "def _progress_callback_for_job", 1
        )[1]
        self.assertIn("self.after(", method)
        self.assertIn("self.status_bar.set_status", method)


if __name__ == "__main__":
    unittest.main()
