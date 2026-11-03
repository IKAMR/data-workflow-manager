"""Regression: choosing repository_operations must never duplicate the directory.

No test in this file creates or changes a Source extraction.
"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.job_preflight_v018_a6 import (inspect_job, propose_work_location)
from app.workbench_api_v018_a3 import DwmWorkbenchAPI
from noark5_workflow.core.job import Job

ROOT = Path(__file__).resolve().parents[1]


class WorkFolderSelectionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.repo = self.root / "example" / "repository_operations"

    def test_work_root_adds_repository_once(self):
        proposal = propose_work_location(self.repo.parent)
        self.assertEqual(proposal.work_root, self.repo.parent)
        self.assertEqual(proposal.work_operations, self.repo)
        self.assertEqual(proposal.selected_role, "work_root")

    def test_selected_repository_operations_is_used_directly(self):
        proposal = propose_work_location(self.repo)
        self.assertEqual(proposal.work_root, self.repo.parent)
        self.assertEqual(proposal.work_operations, self.repo)
        self.assertNotIn("repository_operations/repository_operations", proposal.work_operations.as_posix())
        self.assertEqual(proposal.selected_role, "work_operations")

    def test_existing_dwm_folder_does_not_duplicate_any_level(self):
        proposal = propose_work_location(self.repo / "dwm")
        self.assertEqual(proposal.work_operations, self.repo)
        self.assertEqual(proposal.selected_role, "app_subfolder")

    def test_existing_job_folder_is_not_appended_twice(self):
        proposal = propose_work_location(self.repo / "dwm" / "a01")
        self.assertEqual(proposal.work_operations, self.repo)
        self.assertEqual(proposal.selected_role, "job_subfolder")

    def test_custom_app_folder_is_supported(self):
        proposal = propose_work_location(self.repo / "my-dwm", app_subfolder="my-dwm")
        self.assertEqual(proposal.work_operations, self.repo)

    def test_case_insensitive_repository_detection(self):
        folder = self.root / "RepoSitory_Operations"
        proposal = propose_work_location(folder)
        self.assertEqual(proposal.work_operations, folder)

    def test_unrecognised_nested_folder_is_rejected_without_writes(self):
        selected = self.repo / "unrelated"
        with self.assertRaisesRegex(ValueError, "repository_operations"):
            propose_work_location(selected)
        self.assertFalse(self.repo.exists())

    def test_preflight_proposes_correct_base_without_creating(self):
        source = self.root / "source"
        source.mkdir()
        (source / "arkivstruktur.xml").write_text("<archive/>", encoding="utf-8")
        selected = self.repo
        job = Job("JOB-002", source_root=source, source_extraction=source,
                  work_root=selected, profile_id="noark5",
                  workflow_ids=["metadata_inventory"])
        report = inspect_job(job, effective_work_operations=selected / "dwm")
        self.assertFalse(report.errors, report.issues)
        proposed = [a.path for a in report.actions if a.kind == "set_work_operations"]
        self.assertEqual(proposed, [str(selected)])
        created = [a.path for a in report.actions if a.kind == "mkdir"]
        self.assertEqual(created, [str(selected / "dwm")])
        self.assertFalse(selected.exists())

    def test_ambiguous_work_root_preflight_is_blocked(self):
        source = self.root / "source"
        source.mkdir()
        (source / "arkivstruktur.xml").touch()
        job = Job("JOB-002", source_root=source, source_extraction=source,
                  work_root=self.repo / "unexpected", profile_id="noark5",
                  workflow_ids=["metadata_inventory"])
        report = inspect_job(job, effective_work_operations=None)
        self.assertIn("WORK_ROOT_AMBIGUOUS", {issue.code for issue in report.errors})
        self.assertFalse(self.repo.exists())


class WorkFolderProvisionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "arkivstruktur.xml").touch()
        self.operations = self.root / "work" / "repository_operations"
        self.api = DwmWorkbenchAPI(settings={"app_work_subfolder": "dwm", "arkade5_cli_path": ""})
        self.job = Job("JOB-002", source_root=self.source,
                       source_extraction=self.source, work_root=self.operations,
                       profile_id="noark5", workflow_ids=["metadata_inventory"])
        self.api._batch.add(self.job)

    def test_api_uses_existing_repository_without_duplicate(self):
        report = self.api.preflight_job("JOB-002")
        self.assertFalse(report.errors, report.issues)
        self.assertIn(str(self.operations),
                      [a.path for a in report.actions if a.kind == "set_work_operations"])
        self.assertIn(str(self.operations / "dwm"),
                      [a.path for a in report.actions if a.kind == "mkdir"])
        self.assertFalse(self.operations.exists())

    def test_user_consent_is_required_and_canonical_root_is_saved(self):
        report = self.api.preflight_job("JOB-002")
        with self.assertRaises(Exception):
            self.api.provision_preflight("JOB-002", approved_report=report, consent=False)
        self.assertIsNone(self.job.work_operations)
        self.assertFalse(self.operations.exists())

        result = self.api.provision_preflight("JOB-002", approved_report=report, consent=True)
        self.assertFalse(result.errors, result.issues)
        self.assertEqual(self.job.work_root, self.operations.parent)
        self.assertEqual(self.job.work_operations, self.operations)
        self.assertTrue((self.operations / "dwm").is_dir())
        self.assertFalse((self.operations / "repository_operations").exists())

    def test_legacy_work_root_preview_is_correct(self):
        preview = self.api.preview_output_subfolder_rule("a01")
        self.assertEqual(len(preview), 1)
        self.assertEqual(preview[0][2], str(self.operations / "dwm" / "a01"))
        self.assertFalse(self.operations.exists())


class WorkFolderGuiContractTests(unittest.TestCase):
    def test_both_work_wizards_use_same_interpreter(self):
        source = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertGreaterEqual(source.count("proposal = propose_work_location("), 2)
        self.assertIn('"work_root": str(proposal.work_root)', source)
        self.assertIn('str(proposal.work_operations)', source)
        self.assertIn('Velg annen Work-mappe', source)


if __name__ == "__main__":
    unittest.main()
