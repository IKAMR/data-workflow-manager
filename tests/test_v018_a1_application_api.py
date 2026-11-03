"""v0.1.8-a1 public API regression tests (no GUI/display required)."""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from app.application_api import DwmApiError, DwmApplication
from noark5_workflow.core.job import Job, JobBatch, JobStatus
from noark5_workflow.core.job_store import save_job_list

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class _Outcome:
    ok: bool = True


class _FakeRunner:
    """Prove the boundary delegates execution without GUI or disk scanning."""
    def __init__(self):
        self.work_seen = None
        self.job_seen = None
        self.cancelled = None

    def run(self, job, *, progress_cb, log_cb, state_cb, cancelled_cb):
        self.work_seen = job._effective_work_operations
        self.job_seen = job
        self.cancelled = cancelled_cb
        log_cb("start")
        progress_cb(0.5, "halvveis")
        job.status = JobStatus.OK
        job.progress = 1.0
        job.next_operation_index = len(job.workflow_ids)
        state_cb(job)
        return _Outcome()

    def continue_job(self, job, **callbacks):
        return self.run(job, **callbacks)


class V018A1ApplicationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "uttrekk"
        self.source.mkdir()
        self.content = self.root / "annen-disk" / "work-content"
        self.operations = self.root / "work-operations"
        self.aip = self.root / "aip"
        self.path = self.root / "test.n5jobs"

    def _make_list(self, *, second=False, completed=False):
        batch = JobBatch()
        job = Job(
            job_id="JOB-001", name="1502_024", source_root=self.source,
            source_extraction=self.source,
            work_root=self.root / "work-root",
            work_content=self.content,
            work_operations=self.operations,
            archive_root=self.aip,
            workflow_ids=["test-operation"],
            status=JobStatus.OK if completed else JobStatus.READY,
        )
        batch.add(job)
        if second:
            batch.add(Job(job_id="JOB-002", name="1502_025",
                          source_root=self.source, source_extraction=self.source,
                          work_operations=self.operations,
                          workflow_ids=["test-operation"]))
        batch.output_subfolder_rule = "<jobid>"
        save_job_list(self.path, batch, active_job_id="JOB-001", app_version="0.1.7")
        return job

    def test_imports_are_independent_of_gui(self):
        source = (ROOT / "app" / "application_api.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        for name in imports:
            self.assertFalse(name.split(".")[0] in {"gui", "tkinter", "customtkinter", "PySide6", "PyQt6"}, name)

    def test_open_and_inspect_does_not_modify_joblist_or_storage(self):
        self._make_list()
        original = self.path.read_bytes()
        app = DwmApplication(settings={"app_work_subfolder": "dwm"})
        snapshot = app.open_job_list(self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(len(snapshot.jobs), 1)
        view = snapshot.jobs[0]
        self.assertEqual(view.source_extraction, str(self.source))
        self.assertEqual(view.work_content, str(self.content))
        self.assertEqual(view.work_operations, str(self.operations))
        self.assertEqual(view.archive_root, str(self.aip))
        self.assertEqual(view.effective_work_operations, str(self.operations / "dwm" / "JOB-001"))
        self.assertEqual(app.check_storage(), ())
        self.assertEqual(app.poll_events()[0].kind, "joblist.opened")

    def test_select_and_save_uses_existing_n5jobs_format(self):
        self._make_list()
        app = DwmApplication(settings={"app_work_subfolder": "dwm"})
        app.open_job_list(self.path)
        self.assertEqual(app.select_job("JOB-001").job_id, "JOB-001")
        with self.assertRaises(DwmApiError):
            app.select_job("JOB-999")
        app.save_job_list()
        contents = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(contents["format_version"], 4)
        self.assertEqual(contents["jobs"][0]["work_content"], str(self.content))
        self.assertEqual(contents["jobs"][0]["work_operations"], str(self.operations))
        self.assertEqual(contents["jobs"][0]["archive_root"], str(self.aip))
        self.assertEqual(contents["active_job_id"], "JOB-001")

    def test_distinct_per_job_paths_are_not_collisions(self):
        self._make_list(second=True)
        app = DwmApplication(settings={"app_work_subfolder": "dwm"})
        snap = app.open_job_list(self.path)
        self.assertEqual(app.check_storage(), ())
        self.assertNotEqual(snap.jobs[0].effective_work_operations,
                            snap.jobs[1].effective_work_operations)

    def test_run_delegates_to_headless_runner_without_rewriting_role(self):
        self._make_list()
        runner = _FakeRunner()
        app = DwmApplication(settings={"app_work_subfolder": "dwm"},
                             runner_factory=lambda settings: runner)
        app.open_job_list(self.path)
        self.assertTrue(app.run_job("JOB-001"))
        self.assertEqual(runner.work_seen, self.operations / "dwm" / "JOB-001")
        self.assertEqual(runner.job_seen.work_operations, self.operations)
        self.assertFalse(hasattr(runner.job_seen, "_effective_work_operations"))
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["jobs"][0]["work_operations"], str(self.operations))
        events = [event.kind for event in app.poll_events()]
        self.assertIn("run.progress", events)
        self.assertIn("run.log", events)
        self.assertIn("run.finished", events)

    def test_completed_job_requires_explicit_rerun(self):
        self._make_list(completed=True)
        app = DwmApplication(settings={"app_work_subfolder": "dwm"},
                             runner_factory=lambda settings: _FakeRunner())
        app.open_job_list(self.path)
        with self.assertRaisesRegex(DwmApiError, "godkjenning"):
            app.run_job("JOB-001")
        self.assertTrue(app.run_job("JOB-001", allow_rerun=True))

    def test_worker_exception_is_visible_and_not_left_running(self):
        self._make_list()

        class BrokenRunner:
            def run(self, job, **callbacks):
                job.status = JobStatus.RUNNING
                raise RuntimeError("simulert feil")

        app = DwmApplication(settings={"app_work_subfolder": "dwm"},
                             runner_factory=lambda settings: BrokenRunner())
        app.open_job_list(self.path)
        with self.assertRaisesRegex(RuntimeError, "simulert"):
            app.run_job("JOB-001")
        self.assertEqual(app.workspace().jobs[0].status, JobStatus.FAILED.value)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["jobs"][0]["status"], JobStatus.FAILED.value)
        self.assertIn("run.error", [event.kind for event in app.poll_events()])

    def test_no_implicit_storage_directory_creation(self):
        self._make_list()
        app = DwmApplication(settings={"app_work_subfolder": "dwm"})
        app.open_job_list(self.path)
        self.assertFalse((self.operations / "dwm").exists())
        self.assertFalse(self.content.exists())
        self.assertFalse(self.aip.exists())


if __name__ == "__main__":
    unittest.main()
