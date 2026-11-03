"""v0.1.8-a8: persistent run logging, independent Qt docks and Work selection."""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.run_log_history_v018_a8 import RunLogStore
from app.result_navigation_v018_a8 import latest_depot_report

ROOT = Path(__file__).resolve().parents[1]


class A8LogStoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.work = self.root / "work" / "repository_operations" / "dwm"

    def test_listing_empty_is_read_only(self):
        store = RunLogStore(self.work, "JOB-002")
        self.assertEqual(store.list_runs(), ())
        self.assertFalse(self.work.exists())

    def test_one_run_is_persistent_and_can_be_reopened(self):
        store = RunLogStore(self.work, "JOB-002")
        writer = store.begin(job_name="Documaster", job_list_path="test.n5jobs")
        writer.append("START: Noark 5-test")
        writer.append("OK: Noark 5-test")
        writer.finish("finished")
        reopened = RunLogStore(self.work, "JOB-002")
        history = reopened.list_runs()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].status, "finished")
        content = reopened.read(history[0].run_id)
        self.assertIn("START: Noark 5-test", content)
        self.assertIn("OK: Noark 5-test", content)
        self.assertIn("Jobbliste: test.n5jobs", content)
        self.assertTrue(history[0].log_path.is_relative_to(self.work))

    def test_log_is_flushed_before_finish(self):
        store = RunLogStore(self.work, "JOB-001")
        writer = store.begin(job_name="Test")
        writer.append("æ ø å – ü")
        self.assertIn("æ ø å – ü", store.read(writer.run_id))
        self.assertEqual(store.list_runs()[0].status, "running")
        writer.finish("stopped")
        self.assertEqual(store.list_runs()[0].status, "stopped")

    def test_runs_from_two_jobs_are_separate(self):
        a = RunLogStore(self.work, "JOB-001")
        b = RunLogStore(self.work, "JOB-002")
        w1 = a.begin(job_name="A")
        w1.append("Secret of job A")
        w1.finish()
        w2 = b.begin(job_name="B")
        w2.append("Only job B")
        w2.finish()
        self.assertEqual(len(a.list_runs()), 1)
        self.assertNotIn("Secret of job A", b.read(w2.run_id))
        self.assertNotEqual(a.folder, b.folder)

    def test_each_run_uses_a_unique_file(self):
        store = RunLogStore(self.work, "JOB-002")
        a = store.begin(job_name="Job")
        a.finish()
        b = store.begin(job_name="Job")
        b.finish()
        self.assertNotEqual(a.run_id, b.run_id)
        self.assertEqual(len(store.list_runs()), 2)

    def test_invalid_job_id_and_run_id_are_rejected(self):
        with self.assertRaises(ValueError):
            RunLogStore(self.work, "../../source")
        store = RunLogStore(self.work, "JOB-001")
        with self.assertRaises(ValueError):
            store.read("../../bad")
        self.assertFalse(self.work.exists())

    def test_tail_read_never_truncates_the_original(self):
        store = RunLogStore(self.work, "JOB-001")
        writer = store.begin(job_name="Test")
        for i in range(200):
            writer.append("Evidens-%03d " % i + "z" * 40)
        writer.finish()
        tail = store.read(writer.run_id, max_bytes=1500)
        self.assertIn("Viser siste del", tail)
        self.assertIn("Evidens-199", tail)
        self.assertGreater(writer.log_path.stat().st_size, len(tail.encode("utf-8")))

    def test_only_manifest_matching_job_id_is_listed(self):
        store = RunLogStore(self.work, "JOB-002")
        writer = store.begin(job_name="Test")
        writer.finish()
        metadata = store.folder / (writer.run_id + ".json")
        metadata.write_text(metadata.read_text(encoding="utf-8").replace("JOB-002", "JOB-007"), encoding="utf-8")
        self.assertEqual(store.list_runs(), ())


class A8ReportNavigationTests(unittest.TestCase):
    def test_report_lookup_is_bounded_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(latest_depot_report(root))
            self.assertEqual(list(root.iterdir()), [])
            reports = root / "noark5_reports" / "depot_validation"
            a = reports / "JOB-001_RUN-001" / "depot_validation_report.html"
            b = reports / "JOB-001_RUN-002" / "depot_validation_report.html"
            a.parent.mkdir(parents=True)
            b.parent.mkdir(parents=True)
            a.write_text("old", encoding="utf-8")
            b.write_text("new", encoding="utf-8")
            self.assertEqual(latest_depot_report(root), b)
            self.assertEqual(a.read_text(encoding="utf-8"), "old")


class A8QtContractTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        ast.parse(self.source)

    def test_independent_log_views_are_dockable(self):
        for text in ('"Kjørelogg"', '"Kjøreløp"', '"Systemlogg"',
                     'self._dock("log"', 'self._dock("run"', 'self._dock("system"'):
            self.assertIn(text, self.source)

    def test_history_and_follow_mode_are_wired(self):
        for text in ('self.api.run_log_history(job_id)', 'self.api.read_run_log(job_id, run_id)',
                     '"Følg siste linje"', '"Vis kjørelogg automatisk ved jobbstart"',
                     'self._a8_refresh_job_log(force=True)'):
            self.assertIn(text, self.source)

    def test_user_can_float_log_and_select_other_work_with_confirmation(self):
        for text in ('viewer = DetachedJobLogWindow()',
                     '"Velg annen Work-mappe"',
                     '"Bruk denne mappen"',
                     'Ingen filer eller mapper opprettes, flyttes eller slettes nå.',
                     'self.api.preflight_job(job_id)', 'approved_report=report, consent=True'):
            self.assertIn(text, self.source)

    def test_ui_does_not_implement_analysis_engine(self):
        self.assertNotIn("from gui.persistent_app", self.source)
        self.assertIn("self.api.run_job(", self.source)
        self.assertNotIn("Noark5Extraction.detect(", self.source)


class A8ApiIntegrationTests(unittest.TestCase):
    def test_real_facade_persists_job_log_across_joblist_reload(self):
        # The delta does not bundle a clone of the existing DWM core.
        if not (ROOT / "noark5_workflow" / "core" / "job.py").is_file():
            self.skipTest("Requires the complete DWM repository, not the isolated delta")
        from app.workbench_api_v018_a3 import DwmWorkbenchAPI
        from noark5_workflow.core.job import Job, JobStatus

        class FakeRunner:
            def run(self, job, *, progress_cb, log_cb, cancelled_cb, state_cb):
                job.status = JobStatus.RUNNING
                state_cb(job)
                log_cb("START: Metadataoversikt")
                progress_cb(0.5, "Halvveis")
                log_cb("OK: Metadataoversikt")
                job.next_operation_index = 1
                job.progress = 1.0
                job.status = JobStatus.OK
                job.message = "Workflow fullført"
                state_cb(job)
                return SimpleNamespace(ok=True)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "arkivstruktur.xml").write_text("<archive/>", encoding="utf-8")
            work = root / "work" / "repository_operations"
            (work / "dwm").mkdir(parents=True)
            job = Job("JOB-002", source_root=source, source_extraction=source,
                      work_root=work.parent, work_operations=work,
                      profile_id="noark5", workflow_ids=["metadata_inventory"])
            api = DwmWorkbenchAPI(settings={"app_work_subfolder": "dwm", "arkade5_cli_path": ""},
                                  runner_factory=lambda _settings: FakeRunner())
            api._batch.add(job)
            path = api.save_job_list(root / "test.n5jobs")
            self.assertTrue(api.run_job("JOB-002"))
            records = api.run_log_history("JOB-002")
            self.assertEqual(len(records), 1)
            self.assertIn("OK: Metadataoversikt", api.read_run_log("JOB-002", records[0].run_id))
            reopened = DwmWorkbenchAPI(settings={"app_work_subfolder": "dwm", "arkade5_cli_path": ""})
            reopened.open_job_list(path)
            self.assertEqual(len(reopened.run_log_history("JOB-002")), 1)
            self.assertIn("START: Metadataoversikt", reopened.read_run_log("JOB-002", records[0].run_id))


if __name__ == "__main__":
    unittest.main()
