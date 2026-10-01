from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest

from noark5_workflow.external_tools.arkade5 import (
    configured_arkade5_cli,
    inspect_arkade5_cli,
)
from settings import DEFAULT_CONFIG

ROOT = Path(__file__).resolve().parents[1]


class V016A263Arkade5CliSetupTests(unittest.TestCase):
    def test_default_config_has_blank_arkade5_cli_path(self):
        self.assertIn("arkade5_cli_path", DEFAULT_CONFIG)
        self.assertEqual(DEFAULT_CONFIG["arkade5_cli_path"], "")

    def test_configured_path_is_read_without_hardcoded_installation(self):
        path = configured_arkade5_cli({"arkade5_cli_path": r"C:\\tools\\Arkade5\\Arkivverket.Arkade.CLI.exe"})
        self.assertIsNotNone(path)
        source = (ROOT / "noark5_workflow" / "external_tools" / "arkade5.py").read_text(encoding="utf-8")
        self.assertNotIn(r"C:\\prog\\Arkade5CLI", source)

    def test_missing_configuration_is_explicit(self):
        status = inspect_arkade5_cli({})
        self.assertFalse(status.ok)
        self.assertIn("ikke konfigurert", status.message)

    def test_missing_executable_is_explicit(self):
        status = inspect_arkade5_cli(Path("definitely-missing-Arkade5CLI.exe"))
        self.assertFalse(status.ok)
        self.assertFalse(status.exists)
        self.assertIn("finnes ikke", status.message)

    def test_version_is_detected_through_generic_cli_runner(self):
        with tempfile.TemporaryDirectory() as temp:
            exe = Path(temp) / "Arkivverket.Arkade.CLI.exe"
            exe.write_text("unit-test placeholder", encoding="utf-8")
            fake_result = SimpleNamespace(
                launch_error="",
                stdout="Arkade 5 CLI 2.13.1\n",
                stderr="",
                tool_id="arkade5",
            )
            with patch(
                "noark5_workflow.external_tools.arkade5.run_external_cli",
                return_value=fake_result,
            ) as runner:
                status = inspect_arkade5_cli(exe)

            self.assertTrue(status.ok)
            self.assertEqual(status.version, "2.13.1")
            self.assertEqual(status.version_source, "cli")
            self.assertEqual(status.probe_args, ("--version",))
            self.assertIs(status.probe_result, fake_result)
            runner.assert_called_once()

    def test_version_can_fall_back_to_installation_path_without_launching_placeholder(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "Arkade5CLI-2.12.3"
            folder.mkdir()
            exe = folder / "Arkivverket.Arkade.CLI.exe"
            exe.write_text("unit-test placeholder", encoding="utf-8")
            fake_result = SimpleNamespace(
                launch_error="OSError: unit-test placeholder must not execute",
                stdout="",
                stderr="",
                tool_id="arkade5",
            )
            with patch(
                "noark5_workflow.external_tools.arkade5.run_external_cli",
                return_value=fake_result,
            ) as runner:
                status = inspect_arkade5_cli(exe, timeout_seconds=0.01)

            self.assertTrue(status.ok)
            self.assertEqual(status.version, "2.12.3")
            self.assertEqual(status.version_source, "path")
            self.assertEqual(runner.call_count, 3)

    def test_setup_dialog_exposes_path_browse_check_and_persistence(self):
        source = (ROOT / "gui" / "settings_dialog_a26_3.py").read_text(encoding="utf-8")
        self.assertIn('text="Arkade 5 CLI"', source)
        self.assertIn('text="Kontroller"', source)
        self.assertIn("askopenfilename", source)
        self.assertIn('updated["arkade5_cli_path"]', source)
        self.assertIn("inspect_arkade5_cli(value)", source)

    def test_runtime_activates_a263_settings_layer(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        runtime = (ROOT / "gui" / "persistent_app_a26_3.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a26_3 import run_gui", main)
        self.assertIn("class WorkflowApp(A26_2WorkflowApp)", runtime)
        self.assertIn("SettingsDialog(self, self.settings, self._save_settings)", runtime)

    def test_version_is_a263(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertRegex(version, r'VERSION\s*=\s*"0\.1\.6-a26(?:\.\d+)?"')


if __name__ == "__main__":
    unittest.main()
