from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.external_tools.cli_runner import (
    ExternalCliRequest,
    run_external_cli,
)


class V016A26ExternalCliRunnerTests(unittest.TestCase):
    def test_stdout_stderr_exit_code_and_manifest_are_separate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stdout_path = root / "stdout.txt"
            stderr_path = root / "stderr.txt"
            manifest_path = root / "run.json"

            result = run_external_cli(
                ExternalCliRequest(
                    executable=sys.executable,
                    args=(
                        "-c",
                        "import sys; print('OUT'); print('ERR', file=sys.stderr); sys.exit(7)",
                    ),
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    manifest_path=manifest_path,
                    tool_id="test-tool",
                    operation_id="test-operation",
                    job_id="JOB-001",
                    run_id="RUN-001",
                )
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.exit_code, 7)
            self.assertEqual(result.stdout.strip(), "OUT")
            self.assertEqual(result.stderr.strip(), "ERR")
            self.assertEqual(stdout_path.read_text(encoding="utf-8").strip(), "OUT")
            self.assertEqual(stderr_path.read_text(encoding="utf-8").strip(), "ERR")

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["tool_id"], "test-tool")
            self.assertEqual(manifest["operation_id"], "test-operation")
            self.assertEqual(manifest["job_id"], "JOB-001")
            self.assertEqual(manifest["run_id"], "RUN-001")
            self.assertEqual(manifest["exit_code"], 7)
            self.assertNotIn("content", manifest["stdout"])
            self.assertNotIn("content", manifest["stderr"])

    def test_working_directory_and_environment_overlay_are_passed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            code = (
                "import os; "
                "print(os.getcwd()); "
                "print(os.environ.get('DWM_EXTERNAL_TEST', ''))"
            )
            result = run_external_cli(
                ExternalCliRequest(
                    executable=sys.executable,
                    args=("-c", code),
                    cwd=root,
                    env={"DWM_EXTERNAL_TEST": "works"},
                )
            )
            lines = result.stdout.strip().splitlines()
            self.assertTrue(result.ok)
            self.assertEqual(Path(lines[0]).resolve(), root.resolve())
            self.assertEqual(lines[1], "works")

    def test_missing_executable_is_structured_failure_not_exception(self):
        missing = "dwm-this-executable-does-not-exist-12345"
        result = run_external_cli(ExternalCliRequest(executable=missing))
        self.assertFalse(result.ok)
        self.assertIsNone(result.exit_code)
        self.assertTrue(result.launch_error)
        self.assertIn(missing, result.stderr)

    def test_timeout_is_structured_failure(self):
        result = run_external_cli(
            ExternalCliRequest(
                executable=sys.executable,
                args=("-c", "import time; time.sleep(2)"),
                timeout_seconds=0.1,
            )
        )
        self.assertFalse(result.ok)
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)
        self.assertIn("timeout", result.stderr.lower())

    def test_runner_uses_argument_vector_and_never_shell(self):
        source = Path("noark5_workflow/external_tools/cli_runner.py").read_text(encoding="utf-8")
        self.assertIn("shell=False", source)
        self.assertIn("list(argv)", source)
        self.assertNotIn("shell=True", source)

    def test_version_is_a26(self):
        version = Path("version.py").read_text(encoding="utf-8")
        self.assertRegex(version, r'VERSION\s*=\s*"0\.1\.6-a26(?:\.\d+)?"')


if __name__ == "__main__":
    unittest.main()
