"""v0.1.8-a6: read-only preflight, explicit consent and safe Work provisioning."""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.job_preflight_v018_a6 import (
    check_extraction_folder, inspect_job, paths_to_create,
)
from app.workbench_api_v018_a3 import DwmWorkbenchAPI, DwmApiError
from noark5_workflow.core.job import Job, JobBatch, JobStatus
from noark5_workflow.core.job_store import save_job_list

ROOT = Path(__file__).resolve().parents[1]


class PreflightSourceAndFolderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.extraction = self.root / "package" / "content" / "uttrekk"
        self.extraction.mkdir(parents=True)
        (self.extraction / "arkivstruktur.xml").write_text("<xml />", encoding="utf-8")
        self.work = self.root / "work"
        self.work.mkdir()

    def job(self, **overrides):
        data = dict(
            job_id="JOB-001", source_root=self.extraction.parent,
            source_extraction=self.extraction, source_unzipped=None,
            work_root=self.work, work_operations=self.work / "repository_operations",
            archive_root=None, profile_id="noark5",
            workflow_ids=["metadata_inventory"],
        )
        data.update(overrides)
        return SimpleNamespace(**data)

    def test_correct_source_detected_without_opening_document_payload(self):
        (self.extraction / "DOKUMENT").mkdir()
        self.assertEqual(check_extraction_folder(self.extraction), ())

    def test_unpacked_field_does_not_fall_back_to_extraction(self):
        job = self.job(source_extraction=None, source_unzipped=self.extraction)
        report = inspect_job(job, effective_work_operations=self.work / "repository_operations" / "dwm")
        self.assertIn("EXTRACTION_ROLE_MISSING", {issue.code for issue in report.errors})
        self.assertFalse(report.ready)
        self.assertFalse((self.work / "repository_operations").exists())

    def test_wrong_parent_folder_blocked_with_suggested_child(self):
        issues = check_extraction_folder(self.extraction.parent)
        self.assertEqual(issues[0].code, "NOARK5_MARKER_NOT_FOUND")
        self.assertIn(str(self.extraction), issues[0].message)

    def test_missing_effective_dwm_folder_is_a_proposed_action_not_a_write(self):
        effective = self.work / "repository_operations" / "dwm" / "a01"
        report = inspect_job(self.job(), effective_work_operations=effective)
        self.assertFalse(report.errors)
        self.assertEqual(paths_to_create(report.actions), (effective,))
        self.assertFalse(effective.exists())

    def test_work_root_only_proposes_role_assignment_and_full_folder(self):
        target = self.work / "repository_operations" / "dwm" / "a01"
        report = inspect_job(
            self.job(work_operations=None), effective_work_operations=target,
        )
        self.assertEqual({a.kind for a in report.actions}, {"set_work_operations", "mkdir"})
        self.assertEqual(paths_to_create(report.actions), (target,))
        self.assertFalse(target.exists())

    def test_source_work_overlap_is_blocking_not_createable(self):
        target = self.extraction / "dwm" / "a01"
        report = inspect_job(
            self.job(work_operations=self.extraction / "dwm"),
            effective_work_operations=target,
        )
        self.assertIn("SOURCE_WORK_OVERLAP", {i.code for i in report.errors})

    def test_relative_work_paths_must_not_create_project_directories(self):
        report = inspect_job(
            self.job(work_operations=Path(".")),
            effective_work_operations=Path("dwm") / "a01",
        )
        self.assertIn("RELATIVE_WORK", {issue.code for issue in report.errors})
        self.assertFalse(report.ready)

    def test_dias_packaging_proposes_aip_only_when_configured(self):
        job = self.job(workflow_ids=["dias_package"], archive_root=self.root / "aip")
        report = inspect_job(job, effective_work_operations=self.work / "repository_operations" / "dwm")
        self.assertIn(self.root / "aip", paths_to_create(report.actions))
        self.assertFalse((self.root / "aip").exists())
        missing = inspect_job(self.job(workflow_ids=["dias_package"]), effective_work_operations=self.work / "repository_operations" / "dwm")
        self.assertIn("AIP_NOT_CONFIGURED", {i.code for i in missing.errors})

    def test_aip_cannot_be_created_inside_source(self):
        archive = self.extraction / "aip"
        report = inspect_job(
            self.job(workflow_ids=["dias_package"], archive_root=archive),
            effective_work_operations=self.work / "repository_operations" / "dwm",
        )
        self.assertIn("SOURCE_AIP_OVERLAP", {issue.code for issue in report.errors})
        self.assertFalse(archive.exists())

    def test_missing_configured_work_content_is_in_consent_plan(self):
        content = self.work / "content"
        report = inspect_job(
            self.job(work_content=content),
            effective_work_operations=self.work / "repository_operations" / "dwm",
        )
        self.assertIn(content, paths_to_create(report.actions))
        self.assertFalse(content.exists())

    def test_existing_work_file_blocks_provision(self):
        marker = self.work / "repository_operations"
        marker.write_text("cannot overwrite", encoding="utf-8")
        report = inspect_job(self.job(), effective_work_operations=marker / "dwm" / "a01")
        self.assertIn("WORK_IS_FILE", {i.code for i in report.errors})
        self.assertEqual(marker.read_text(encoding="utf-8"), "cannot overwrite")


class PreflightApiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "arkivstruktur.xml").write_text("<x/>", encoding="utf-8")
        self.work = self.root / "work"
        self.work.mkdir()
        batch = JobBatch()
        batch.add(Job(
            "JOB-001", source_root=self.source, source_extraction=self.source,
            work_root=self.work, profile_id="noark5",
            workflow_ids=["metadata_inventory"],
        ))
        self.path = self.root / "jobs.n5jobs"
        save_job_list(self.path, batch, active_job_id="JOB-001", app_version="0.1.8-a6")
        self.api = DwmWorkbenchAPI(settings={"app_work_subfolder": "dwm"})
        self.api.open_job_list(self.path)

    def test_preflight_is_read_only_and_never_sets_work_role(self):
        original = self.path.read_bytes()
        report = self.api.preflight_job("JOB-001")
        self.assertEqual({a.kind for a in report.actions}, {"set_work_operations", "mkdir"})
        self.assertIsNone(self.api._batch.get("JOB-001").work_operations)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertFalse((self.work / "repository_operations").exists())

    def test_run_rejects_missing_work_before_runner_construction(self):
        called = []
        self.api._runner_factory = lambda _cfg: called.append(True)
        with self.assertRaisesRegex(DwmApiError, "mapper"):
            self.api.run_job("JOB-001")
        self.assertEqual(called, [])
        self.assertFalse((self.work / "repository_operations").exists())

    def test_consent_required_and_exact_work_path_created_after_yes(self):
        report = self.api.preflight_job("JOB-001")
        with self.assertRaisesRegex(DwmApiError, "godkjenning"):
            self.api.provision_preflight("JOB-001", approved_report=report, consent=False)
        self.assertFalse((self.work / "repository_operations").exists())
        after = self.api.provision_preflight("JOB-001", approved_report=report, consent=True)
        self.assertTrue(after.ready)
        self.assertEqual(self.api._batch.get("JOB-001").work_operations, self.work / "repository_operations")
        self.assertTrue((self.work / "repository_operations" / "dwm").is_dir())
        self.assertTrue(self.api.dirty)
        # Source file remains intact; unrelated output is not generated.
        self.assertTrue((self.source / "arkivstruktur.xml").is_file())
        self.assertFalse((self.root / "aip").exists())

    def test_stale_confirmation_rejected_without_side_effects(self):
        report = self.api.preflight_job("JOB-001")
        replacement = self.root / "work2"
        replacement.mkdir()
        self.api.update_storage("JOB-001", {"work_root": replacement})
        with self.assertRaisesRegex(DwmApiError, "endret"):
            self.api.provision_preflight("JOB-001", approved_report=report, consent=True)
        self.assertFalse((self.work / "repository_operations").exists())
        self.assertFalse((replacement / "repository_operations").exists())

    def test_work_folder_does_not_create_until_consent_even_when_set(self):
        self.api.update_storage("JOB-001", {"work_operations": self.work / "repository_operations"})
        report = self.api.preflight_job("JOB-001")
        self.assertEqual(len(report.actions), 1)
        self.assertEqual(report.actions[0].kind, "mkdir")
        self.assertFalse((self.work / "repository_operations" / "dwm").exists())
        self.api.provision_preflight("JOB-001", approved_report=report, consent=True)
        self.assertTrue((self.work / "repository_operations" / "dwm").is_dir())

    def test_source_wrong_role_blocks_creation_even_with_approval(self):
        self.api.update_storage("JOB-001", {"source_extraction": None, "source_unzipped": self.source})
        report = self.api.preflight_job("JOB-001")
        self.assertTrue(report.errors)
        with self.assertRaisesRegex(DwmApiError, "blokkert"):
            self.api.provision_preflight("JOB-001", approved_report=report, consent=True)
        self.assertFalse((self.work / "repository_operations").exists())

    def test_approved_preflight_can_execute_using_existing_runner(self):
        report = self.api.preflight_job("JOB-001")
        self.api.provision_preflight("JOB-001", approved_report=report, consent=True)
        self.api.save_job_list()

        class FakeRunner:
            def run(self, job, *, progress_cb, log_cb, cancelled_cb, state_cb):
                log_cb("start")
                job.status = JobStatus.OK
                job.progress = 1.0
                job.next_operation_index = len(job.workflow_ids)
                state_cb(job)
                return SimpleNamespace(ok=True)

        self.api._runner_factory = lambda _cfg: FakeRunner()
        self.assertTrue(self.api.run_job("JOB-001"))
        self.assertEqual(self.api.workspace().jobs[0].status, "Ferdig")

    def test_a6_qt_has_confirmation_and_beginner_setup(self):
        ui = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        ast.parse(ui)
        for expected in (
            "def _new_job_easy", "def _review_preflight", "self.api.preflight_job(",
            "self.api.provision_preflight(", "consent=True", "QMessageBox.StandardButton.No",
            "Kontroller / klargjør", "acknowledge_warnings=job_id in warning_approvals",
        ):
            self.assertIn(expected, ui)
        self.assertLess(ui.index("warning_approvals = self._review_preflight"),
                        ui.index("self._worker = Thread(target=run"))


if __name__ == "__main__":
    unittest.main()
