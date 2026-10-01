from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from noark5_workflow.external_tools.cli_runner import ExternalCliRequest, run_external_cli
from noark5_workflow.external_tools.arkade5_jobs import ARKADE5_NOARK5, run_arkade5_plan

ROOT = Path(__file__).resolve().parents[1]


class V016A267LiveCliStatusTests(unittest.TestCase):
    def test_generic_runner_streams_stdout_and_stderr_without_losing_evidence(self):
        events = []
        code = (
            "import sys,time; "
            "print('STEP 1', flush=True); "
            "time.sleep(0.05); "
            "print('WARN', file=sys.stderr, flush=True); "
            "time.sleep(0.05); "
            "print('STEP 2', flush=True)"
        )
        result = run_external_cli(
            ExternalCliRequest(executable=sys.executable, args=("-c", code)),
            on_output=lambda stream, line: events.append((stream, line.strip())),
        )
        self.assertTrue(result.ok)
        self.assertIn(("stdout", "STEP 1"), events)
        self.assertIn(("stderr", "WARN"), events)
        self.assertIn(("stdout", "STEP 2"), events)
        self.assertIn("STEP 1", result.stdout)
        self.assertIn("STEP 2", result.stdout)
        self.assertIn("WARN", result.stderr)

    def test_arkade_batch_forwards_live_output_with_job_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / "Arkivverket.Arkade.CLI.exe"
            exe.write_text("placeholder", encoding="utf-8")
            source = root / "source"
            source.mkdir()
            work = root / "work"
            work.mkdir()
            plan = SimpleNamespace(
                job_id="JOB-001",
                job_name="test",
                operation=ARKADE5_NOARK5,
                source=source,
                work_operations=work,
                output_dir=work / "run",
                processing_dir=root / "processing",
                args=("test",),
                run_id="RUN-001",
                tool_version="2.13.1",
            )
            seen = []
            fake_result = SimpleNamespace(ok=True, launch_error="", timed_out=False, exit_code=0)

            def fake_runner(request, *, on_output=None):
                self.assertIsNotNone(on_output)
                on_output("stdout", "Validating arkivstruktur.xml\n")
                return fake_result

            with patch("noark5_workflow.external_tools.arkade5_jobs.configured_arkade5_cli", return_value=exe), patch(
                "noark5_workflow.external_tools.arkade5_jobs.run_external_cli", side_effect=fake_runner
            ):
                summary = run_arkade5_plan(
                    {"arkade5_cli_path": str(exe)},
                    [plan],
                    on_output=lambda index, total, active_plan, stream, text: seen.append(
                        (index, total, active_plan.job_id, stream, text.strip())
                    ),
                )
            self.assertEqual(summary.succeeded, 1)
            self.assertEqual(seen, [(1, 1, "JOB-001", "stdout", "Validating arkivstruktur.xml")])

    def test_dialog_has_indeterminate_activity_elapsed_time_and_live_log(self):
        source = (ROOT / "gui" / "arkade5_run_dialog.py").read_text(encoding="utf-8")
        self.assertIn('mode="indeterminate"', source)
        self.assertIn("Denne kjøringen:", source)
        self.assertIn("Live-status fra Arkade", source)
        self.assertIn("_poll_output", source)
        self.assertNotIn("% ferdig", source)

    def test_runtime_activates_a267_and_forwards_output_callback(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        runtime = (ROOT / "gui" / "persistent_app_a26_7.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a26_7 import run_gui", main)
        self.assertIn("class WorkflowApp(A26_6WorkflowApp)", runtime)
        self.assertIn("on_output=on_output", runtime)

    def test_version_is_a267(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertRegex(version, r'VERSION\s*=\s*"0\.1\.6-a26(?:\.(?:7|[89]|[1-9]\d+))?"')


if __name__ == "__main__":
    unittest.main()
