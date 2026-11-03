"""Tests for the generic Setup and the restored .n5jobs Work subfolder rule."""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.application_api import DwmApiError
from app.workbench_api_v018_a3 import DwmWorkbenchAPI
from noark5_workflow.core.job import Job
from noark5_workflow.core.job_store import load_job_list

ROOT = Path(__file__).resolve().parents[1]


class OutputSubfolderRuleTests(unittest.TestCase):
    def setUp(self):
        context = tempfile.TemporaryDirectory()
        self.addCleanup(context.cleanup)
        self.root = Path(context.name)
        self.api = DwmWorkbenchAPI(settings={"app_work_subfolder": "dwm"})
        self.api._batch.add(Job("JOB-001", work_operations=self.root / "operations-1"))
        self.api._batch.add(Job("JOB-002", work_operations=self.root / "operations-2"))

    def test_preview_is_read_only(self):
        preview = self.api.preview_output_subfolder_rule("a01")
        self.assertEqual(len(preview), 2)
        self.assertIn("operations-1", preview[0][1])
        self.assertTrue(preview[0][2].endswith(str(Path("dwm") / "a01")))
        self.assertEqual(self.api.output_subfolder_rule, "")
        self.assertFalse((self.root / "operations-1").exists())

    def test_rule_requires_explicit_confirmation(self):
        with self.assertRaisesRegex(DwmApiError, "bekreft"):
            self.api.set_output_subfolder_rule("a01")
        self.assertEqual(self.api.output_subfolder_rule, "")
        self.api.set_output_subfolder_rule("a01", confirm_changes=True)
        self.assertTrue(self.api.dirty)
        self.assertEqual(self.api.output_subfolder_rule, "a01")
        self.assertFalse((self.root / "operations-1").exists())

    def test_joblist_rule_persists_in_n5jobs(self):
        self.api.set_output_subfolder_rule("a01", confirm_changes=True)
        output = self.api.save_job_list(self.root / "jobs.n5jobs")
        loaded = load_job_list(output)
        self.assertEqual(loaded.output_subfolder_rule, "a01")
        self.assertEqual(getattr(loaded.batch, "output_subfolder_rule"), "a01")

    def test_invalid_rule_rejected_without_changes(self):
        with self.assertRaisesRegex(DwmApiError, "Ugyldig"):
            self.api.preview_output_subfolder_rule("<wrong>")
        self.assertEqual(self.api.output_subfolder_rule, "")

    def test_colliding_work_folders_rejected(self):
        same = self.root / "same"
        self.api._batch.get("JOB-001").work_operations = same
        self.api._batch.get("JOB-002").work_operations = same
        with self.assertRaises(DwmApiError):
            self.api.set_output_subfolder_rule("a01", confirm_changes=True)
        self.assertEqual(self.api.output_subfolder_rule, "")

    def test_work_root_preview_uses_proposed_repository_operations(self):
        job = self.api._batch.get("JOB-002")
        job.work_operations = None
        job.work_root = self.root / "work-root"
        preview = self.api.preview_output_subfolder_rule("a01")
        self.assertTrue(preview[1][2].endswith(
            str(Path("work-root") / "repository_operations" / "dwm" / "a01")
        ))
        self.assertFalse((self.root / "work-root").exists())

    def test_empty_job_list_validates_tokens(self):
        self.api._batch.clear()
        with self.assertRaises(DwmApiError):
            self.api.preview_output_subfolder_rule("<wrong>")


class GeneralSetupTests(unittest.TestCase):
    def test_generic_setup_accepts_existing_visibility_and_path_keys(self):
        api = DwmWorkbenchAPI(settings={"app_work_subfolder": "dwm"})
        updates = {"operation_visibility": 1, "run_log_dir": "C:/logs",
                   "setup_dir": "C:/setup", "job_list_dir": "C:/lists"}
        with patch("app.workbench_api_v018_a3.save_config", side_effect=lambda d: dict(d)):
            api.save_setup(updates)
        self.assertEqual(api.settings["operation_visibility"], 1)
        self.assertEqual(api.settings["job_list_dir"], "C:/lists")

    def test_illegal_visibility_is_rejected(self):
        api = DwmWorkbenchAPI(settings={"app_work_subfolder": "dwm"})
        with self.assertRaises(DwmApiError):
            api.save_setup({"operation_visibility": 9})

    def test_setup_toolbar_has_short_label_and_tabs(self):
        main = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        setup = (ROOT / "gui_qt" / "setup_v018_a7.py").read_text(encoding="utf-8")
        ast.parse(main)
        ast.parse(setup)
        self.assertIn('self.setup_action = self._action("Setup", self._open_setup)', main)
        for title in ("Generelt", "Arbeidsflyt", "Mapper og Work", "Eksterne verktøy"):
            self.assertIn(title, setup)
        self.assertIn('QLabel("Undermappe-regel:")', main)
        self.assertIn("self.api.set_output_subfolder_rule(proposed", main)
        self.assertIn("self.api.save_setup(updates)", setup)


if __name__ == "__main__":
    unittest.main()
