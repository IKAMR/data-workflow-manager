from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A158StartReadyTests(unittest.TestCase):
    def setUp(self):
        self.jobs = (
            ROOT / "gui" / "jobs_window_a17.py"
        ).read_text(encoding="utf-8")
        self.runtime = (
            ROOT / "gui" / "persistent_app_a25.py"
        ).read_text(encoding="utf-8")
        self.main = (
            ROOT / "main.py"
        ).read_text(encoding="utf-8")

    def test_current_runtime_preserves_a25(self):
        self.assertIn(
            "from gui.persistent_app_a25 import WorkflowApp as _A25WorkflowApp",
            self.main,
        )
        self.assertIn(
            "from gui.persistent_app_a27 import run_gui",
            self.main,
        )

    def test_jobs_window_exposes_start_ready(self):
        self.assertIn('text="Start klare"', self.jobs)
        self.assertIn("command=self._start_ready_jobs", self.jobs)

    def test_ready_count_is_visible_in_summary(self):
        self.assertIn("Kjørbare nå:", self.jobs)

    def test_ready_batch_excludes_completed_jobs(self):
        self.assertIn(
            "job.status in {JobStatus.READY, JobStatus.WAITING}",
            self.runtime,
        )
        predicate = self.runtime.split(
            "def _job_is_ready_for_batch", 1
        )[1].split("def _start_ready_jobs", 1)[0]
        self.assertNotIn("JobStatus.OK,", predicate)

    def test_jobs_without_workflow_are_not_run(self):
        self.assertIn("if not job.workflow_ids:", self.runtime)

    def test_waiting_jobs_keep_existing_continue_semantics(self):
        self.assertIn(
            "self._execute_job(job, batch_mode=True)",
            self.runtime,
        )
        self.assertIn("WAITING preserves", self.runtime)

    def test_user_is_told_completed_jobs_are_not_rerun(self):
        self.assertIn(
            "Ferdige jobber blir ikke kjørt på nytt.",
            self.runtime,
        )


if __name__ == "__main__":
    unittest.main()
