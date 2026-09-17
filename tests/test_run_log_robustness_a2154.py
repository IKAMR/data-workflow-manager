import tempfile
import unittest

from app.run_overview_log import RunOverviewLog

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


class RunLogRobustnessA2154Tests(unittest.TestCase):
    def test_log_has_started_status_before_first_job(self):
        with tempfile.TemporaryDirectory() as temp:
            log = RunOverviewLog({"temp_dir": temp, "run_log_dir": ""}, run_type="batch", app_version="0.1.2-a2", planned_jobs=2)
            text = log.path.read_text(encoding="utf-8")
            self.assertIn("Status: STARTET", text)
            self.assertIn("Planlagte jobber: 2", text)

    def test_failure_before_first_job_is_persisted(self):
        with tempfile.TemporaryDirectory() as temp:
            log = RunOverviewLog({"temp_dir": temp, "run_log_dir": ""}, run_type="batch", app_version="0.1.2-a2", planned_jobs=2)
            text = log.fail(RuntimeError("simulert feil")).read_text(encoding="utf-8")
            self.assertIn("Status: FEIL", text)
            self.assertIn("Feil: simulert feil", text)
            self.assertIn("Startede jobber: 0", text)
            self.assertIn("Planlagte jobber: 2", text)

    def test_latest_runtime_normalises_stale_running(self):
        latest = (ROOT / "gui" / "persistent_app_a6.py").read_text(encoding="utf-8")
        core = (ROOT / "noark5_workflow" / "core" / "preflight.py").read_text(encoding="utf-8")
        self.assertIn("self.preflight.normalize_job", latest)
        self.assertIn("job.status == JobStatus.RUNNING", core)
        self.assertIn("job.reset_execution", core)

    def test_batch_worker_has_top_level_exception_logging(self):
        text = (ROOT / "gui" / "persistent_app_a5.py").read_text(encoding="utf-8")
        self.assertIn("overview.fail(exc)", text)
        self.assertIn("BATCH FEIL:", text)

    def test_current_runtime_preserves_robust_runtime_chain(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        a19 = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")
        a18 = (ROOT / "gui" / "persistent_app_a18.py").read_text(encoding="utf-8")
        a17 = (ROOT / "gui" / "persistent_app_a17.py").read_text(encoding="utf-8")
        a13 = (ROOT / "gui" / "persistent_app_a13.py").read_text(encoding="utf-8")
        a6 = (ROOT / "gui" / "persistent_app_a6.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a19", main)
        self.assertIn("A18WorkflowApp", a19)
        self.assertIn("A17WorkflowApp", a18)
        self.assertIn("A13WorkflowApp", a17)
        self.assertIn("persistent_app_a6", a13)
        self.assertIn("A5WorkflowApp", a6)


if __name__ == "__main__":
    unittest.main()
