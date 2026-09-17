import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.run_overview_log import RunOverviewLog
from app.workspace import ensure_workspace, job_list_dir, run_log_dir, setup_dir
from settings import DEFAULT_CONFIG

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceRunLogsA215Tests(unittest.TestCase):
    def test_standard_config_keys_exist(self):
        self.assertIn("run_log_dir", DEFAULT_CONFIG)
        self.assertIn("setup_dir", DEFAULT_CONFIG)
        self.assertIn("job_list_dir", DEFAULT_CONFIG)

    def test_workspace_fallback_dirs(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = {"temp_dir": temp, "run_log_dir": "", "setup_dir": "", "job_list_dir": ""}
            self.assertEqual(run_log_dir(settings), Path(temp) / "logs" / "runs")
            self.assertEqual(setup_dir(settings), Path(temp) / "setup")
            self.assertEqual(job_list_dir(settings), Path(temp) / "joblists")
            paths = ensure_workspace(settings)
            for key in ("run_logs", "setup", "joblists", "work", "cache"):
                self.assertTrue(paths[key].is_dir())

    def test_configured_dirs_override_workspace_fallback(self):
        settings = {"temp_dir": "C:/temp", "run_log_dir": "D:/logs", "setup_dir": "D:/setup", "job_list_dir": "D:/jobs"}
        self.assertEqual(str(run_log_dir(settings)), str(Path("D:/logs")))
        self.assertEqual(str(setup_dir(settings)), str(Path("D:/setup")))
        self.assertEqual(str(job_list_dir(settings)), str(Path("D:/jobs")))

    def test_one_log_per_run_same_format_for_single_and_batch(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = {"temp_dir": temp, "run_log_dir": ""}
            single = RunOverviewLog(settings, run_type="single", app_version="0.1.2-a2")
            job = SimpleNamespace(job_id="JOB-001", name="Test", source_root=Path("C:/source"), output_root=Path("C:/output"), status=SimpleNamespace(value="ok"), message="Workflow fullført")
            single.start_job(job)
            single.finish_job(job)
            single_path = single.finish()
            batch = RunOverviewLog(settings, run_type="batch", app_version="0.1.2-a2")
            batch.start_job(job)
            batch.finish_job(job)
            batch_path = batch.finish()
            self.assertNotEqual(single_path, batch_path)
            for path in (single_path, batch_path):
                text = path.read_text(encoding="utf-8")
                self.assertIn("Run ID:", text)
                self.assertIn("JOBB 1", text)
                self.assertIn("Jobb-ID: JOB-001", text)
                self.assertIn("Source:", text)
                self.assertIn("Output:", text)
                self.assertIn("SAMMENDRAG", text)

    def test_current_runtime_preserves_a215_chain(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        a19 = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")
        a18 = (ROOT / "gui" / "persistent_app_a18.py").read_text(encoding="utf-8")
        a17 = (ROOT / "gui" / "persistent_app_a17.py").read_text(encoding="utf-8")
        a13 = (ROOT / "gui" / "persistent_app_a13.py").read_text(encoding="utf-8")
        runtime = (ROOT / "gui" / "persistent_app_a215.py").read_text(encoding="utf-8")
        a6 = (ROOT / "gui" / "persistent_app_a6.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a19", main)
        self.assertIn("A18WorkflowApp", a19)
        self.assertIn("A17WorkflowApp", a18)
        self.assertIn("A13WorkflowApp", a17)
        self.assertIn("persistent_app_a6", a13)
        self.assertIn("A5WorkflowApp", a6)
        self.assertIn('self._new_run_log("single")', runtime)
        self.assertIn('self._new_run_log("batch")', runtime)


if __name__ == "__main__":
    unittest.main()
