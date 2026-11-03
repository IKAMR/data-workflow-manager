"""Regression coverage for v0.1.8-a7 Setup and Arkade CLI preflight."""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.arkade5_setup_v018_a7 import (
    Arkade5DependencyChecker, find_arkade5_candidates, requires_arkade_cli,
)

ROOT = Path(__file__).resolve().parents[1]


class Arkade5SetupServiceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.exe = self.root / "Arkade5CLI.exe"
        self.exe.write_bytes(b"fake executable for isolated unit test")

    @staticmethod
    def status(*, ok=True, version="2.13.1", source="cli", result=None, message="Arkade CLI"):
        return SimpleNamespace(ok=ok, version=version, version_source=source,
                               message=message, probe_result=result)

    def test_only_executable_arkade_operations_require_cli(self):
        self.assertFalse(requires_arkade_cli(["import_arkade5_reports", "metadata_inventory"]))
        self.assertFalse(requires_arkade_cli([]))
        self.assertTrue(requires_arkade_cli(["arkade5_noark5_test"]))
        self.assertTrue(requires_arkade_cli(["arkade5_pronom_analysis", "import_arkade5_reports"]))

    def test_no_path_error_without_calling_probe(self):
        inspector = Mock()
        result = Arkade5DependencyChecker(inspector=inspector).check({"arkade5_cli_path": ""})
        self.assertEqual(result.severity, "error")
        inspector.assert_not_called()

    def test_relative_path_error(self):
        result = Arkade5DependencyChecker().check({"arkade5_cli_path": "Arkade5CLI.exe"})
        self.assertEqual(result.severity, "error")
        self.assertIn("absolutt", result.message)

    def test_missing_file_error(self):
        result = Arkade5DependencyChecker().check({"arkade5_cli_path": str(self.root / "absent.exe")})
        self.assertEqual(result.severity, "error")
        self.assertIn("finnes ikke", result.message)

    def test_valid_version_probed_and_cached(self):
        inspector = Mock(return_value=self.status())
        checker = Arkade5DependencyChecker(inspector=inspector)
        a = checker.check({"arkade5_cli_path": str(self.exe)})
        b = checker.check({"arkade5_cli_path": str(self.exe)})
        self.assertEqual(a.severity, "ok")
        self.assertEqual(a.version, "2.13.1")
        self.assertEqual(a, b)
        inspector.assert_called_once()
        self.assertLessEqual(inspector.call_args.kwargs["timeout_seconds"], 3.0)
        checker.check({"arkade5_cli_path": str(self.exe)}, refresh=True)
        self.assertEqual(inspector.call_count, 2)
        checker.invalidate()
        checker.check({"arkade5_cli_path": str(self.exe)})
        self.assertEqual(inspector.call_count, 3)

    def test_non_arkade_executable_with_version_is_warning(self):
        other = self.root / "other-tool.exe"
        other.write_bytes(b"test")
        inspector = lambda *_a, **_k: self.status()
        check = Arkade5DependencyChecker(inspector=inspector).check({"arkade5_cli_path": str(other)})
        self.assertEqual(check.severity, "warning")

    def test_cli_nonzero_exit_requires_acknowledgement(self):
        result = SimpleNamespace(launch_error="", timed_out=False, exit_code=1,
                                 stdout="Arkade5 CLI 2.13.1", stderr="")
        inspector = lambda *_a, **_k: self.status(result=result)
        check = Arkade5DependencyChecker(inspector=inspector).check({"arkade5_cli_path": str(self.exe)})
        self.assertEqual(check.severity, "warning")

    def test_version_only_from_path_is_warning(self):
        inspector = lambda *_a, **_k: self.status(source="path")
        result = Arkade5DependencyChecker(inspector=inspector).check({"arkade5_cli_path": str(self.exe)})
        self.assertEqual(result.severity, "warning")
        self.assertIn("ikke bekreftet", result.message)

    def test_cli_launch_failure_cannot_pass_on_version_in_path(self):
        result = SimpleNamespace(launch_error="Kan ikke startes", timed_out=False)
        inspector = lambda *_a, **_k: self.status(source="path", result=result)
        check = Arkade5DependencyChecker(inspector=inspector).check({"arkade5_cli_path": str(self.exe)})
        self.assertEqual(check.severity, "error")

    def test_timeout_is_error(self):
        result = SimpleNamespace(launch_error="", timed_out=True)
        inspector = lambda *_a, **_k: self.status(source="path", result=result)
        check = Arkade5DependencyChecker(inspector=inspector).check({"arkade5_cli_path": str(self.exe)})
        self.assertEqual(check.severity, "error")

    def test_inspector_errors_are_reported_not_crashes(self):
        inspector = Mock(side_effect=OSError("tilgang nektet"))
        check = Arkade5DependencyChecker(inspector=inspector).check({"arkade5_cli_path": str(self.exe)})
        self.assertEqual(check.severity, "error")
        self.assertIn("tilgang nektet", check.message)

    def test_discovery_is_read_only_and_bounded(self):
        program_files = self.root / "Program Files"
        exe = program_files / "Arkade5CLI-2.13.1" / "bin" / "Arkade5CLI.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"local test")
        result = find_arkade5_candidates(env={"PATH": "", "PROGRAMFILES": str(program_files)})
        self.assertIn(exe.resolve(), result)
        self.assertEqual(exe.read_bytes(), b"local test")
        self.assertEqual(list(self.root.rglob("*.json")), [])


class Arkade5A7IntegrationTests(unittest.TestCase):
    def setUp(self):
        from app.workbench_api_v018_a3 import DwmWorkbenchAPI
        from noark5_workflow.core.job import Job
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "uttrekk"
        self.source.mkdir()
        (self.source / "arkivstruktur.xml").write_text("<x/>", encoding="utf-8")
        self.work = self.root / "operations"
        (self.work / "dwm").mkdir(parents=True)
        self.exe = self.root / "Arkade5CLI.exe"
        self.exe.write_bytes(b"test")
        self.api = DwmWorkbenchAPI(settings={
            "app_work_subfolder": "dwm", "arkade5_cli_path": "",
        })
        self.job = Job("JOB-001", source_root=self.source,
                       source_extraction=self.source, work_operations=self.work,
                       profile_id="noark5", workflow_ids=["arkade5_noark5_test"])
        self.api._batch.add(self.job)

    def test_execution_dependency_blocks_unconfigured_cli(self):
        report = self.api.preflight_job("JOB-001")
        self.assertIn("ARKADE5_CLI_ERROR", {issue.code for issue in report.errors})
        self.assertFalse(report.ready)
        from app.application_api import DwmApiError
        with self.assertRaisesRegex(DwmApiError, "Arkade"):
            self.api.run_job("JOB-001")

    def test_import_only_does_not_need_cli(self):
        self.job.workflow_ids = ["import_arkade5_reports"]
        report = self.api.preflight_job("JOB-001")
        self.assertEqual(report.errors, ())
        self.assertTrue(report.ready)

    def test_verified_cli_allows_preflight(self):
        self.job.workflow_ids = ["arkade5_noark5_test", "arkade5_pronom_analysis"]
        self.api.settings["arkade5_cli_path"] = str(self.exe)
        self.api._arkade_checker = Arkade5DependencyChecker(
            inspector=lambda *_a, **_kw: Arkade5SetupServiceTests.status())
        report = self.api.preflight_job("JOB-001")
        self.assertTrue(report.ready, report.issues)

    def test_uncertain_cli_requires_approval(self):
        self.api.settings["arkade5_cli_path"] = str(self.exe)
        self.api._arkade_checker = Arkade5DependencyChecker(
            inspector=lambda *_a, **_kw: Arkade5SetupServiceTests.status(source="path"))
        report = self.api.preflight_job("JOB-001")
        self.assertEqual(report.errors, ())
        self.assertIn("ARKADE5_CLI_WARNING", {issue.code for issue in report.warnings})
        self.assertFalse(report.ready)
        from app.application_api import DwmApiError
        with self.assertRaisesRegex(DwmApiError, "godkjenning"):
            self.api.run_job("JOB-001")

    def test_diagnose_proposed_path_does_not_change_setup(self):
        self.api._arkade_checker = Arkade5DependencyChecker(
            inspector=lambda *_a, **_kw: Arkade5SetupServiceTests.status())
        self.api.check_arkade5_cli(path=str(self.exe))
        self.assertEqual(self.api.settings["arkade5_cli_path"], "")

    def test_setup_rejects_unexpected_settings(self):
        from app.application_api import DwmApiError
        with self.assertRaisesRegex(DwmApiError, "Ukjente"):
            self.api.save_setup({"secret_unexpected_key": "value"})
        self.assertNotIn("secret_unexpected_key", self.api.settings)

    def test_save_setup_uses_shared_config_and_invalidates_cli_cache(self):
        self.api._arkade_checker.check = Mock()
        with patch("app.workbench_api_v018_a3.save_config", side_effect=lambda changes: dict(changes)) as save:
            self.api.save_setup({"arkade5_cli_path": str(self.exe),
                                 "app_work_subfolder": "dwm"})
        save.assert_called_once()
        self.assertEqual(self.api.settings["arkade5_cli_path"], str(self.exe))
        self.assertEqual(self.api.settings["app_work_subfolder"], "dwm")


class Arkade5A7GuiContractTests(unittest.TestCase):
    def test_setup_dialog_and_button_wired_to_same_api(self):
        main = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        setup = (ROOT / "gui_qt" / "setup_v018_a7.py").read_text(encoding="utf-8")
        ast.parse(main)
        ast.parse(setup)
        self.assertIn("self.setup_action = self._action", main)
        self.assertIn("toolbar.addAction(self.setup_action)", main)
        self.assertIn("dialog = DwmSetupDialog(self.api, self)", main)
        self.assertIn("self.api.save_setup(updates)", setup)
        self.assertIn("find_arkade5_candidates()", setup)
        self.assertIn("self.api.check_arkade5_cli(path=path, refresh=True)", setup)
        self.assertIn("if arkade_error:", main)
        self.assertIn("self._open_setup()", main)

    def test_worker_run_is_still_guarded_by_preflight(self):
        source = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        self.assertLess(source.index("warning_approvals = self._review_preflight"),
                        source.index("self._worker = Thread(target=run"))
        api = (ROOT / "app" / "workbench_api_v018_a3.py").read_text(encoding="utf-8")
        self.assertIn("if not requires_arkade_cli(job.workflow_ids):", api)
        self.assertIn('PreflightIssue("ARKADE5_CLI_"', api)


if __name__ == "__main__":
    unittest.main()
