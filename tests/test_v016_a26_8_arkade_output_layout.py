from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from noark5_workflow.external_tools.arkade5_jobs import (
    ARKADE5_NOARK5,
    ARKADE5_PRONOM,
    build_arkade5_plan,
    resolve_arkade5_output_subfolder,
    run_arkade5_plan,
)

ROOT = Path(__file__).resolve().parents[1]


class V016A268ArkadeOutputLayoutTests(unittest.TestCase):
    def _job(self, root: Path):
        source = root / "source" / "content"
        source.mkdir(parents=True)
        work = root / "repository_operations"
        work.mkdir()
        return SimpleNamespace(
            job_id="JOB-001",
            name="sip",
            active_extraction_root=source,
            work_operations=work,
        )

    def test_version_token_resolves_in_configured_subfolder(self):
        self.assertEqual(
            resolve_arkade5_output_subfolder(
                {"arkade5_output_subfolder": "arkade5_<ver>"}, "2.13.1"
            ),
            "arkade5_v2.13.1",
        )
        self.assertEqual(
            resolve_arkade5_output_subfolder(
                {"arkade5_output_subfolder": "arkade5_v2.13.1"}, "2.13.1"
            ),
            "arkade5_v2.13.1",
        )

    def test_plan_uses_only_configured_root_and_operation_folders(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / "Arkivverket.Arkade.CLI.exe"
            exe.write_text("placeholder", encoding="utf-8")
            job = self._job(root)
            fake_status = SimpleNamespace(ok=True, version="2.13.1", message="OK")
            with patch("noark5_workflow.external_tools.arkade5_jobs.inspect_arkade5_cli", return_value=fake_status):
                plans = build_arkade5_plan(
                    {
                        "arkade5_cli_path": str(exe),
                        "arkade5_output_subfolder": "arkade5_<ver>",
                    },
                    [job],
                    [ARKADE5_NOARK5, ARKADE5_PRONOM],
                )
            self.assertEqual(plans[0].output_dir, job.work_operations / "arkade5_v2.13.1" / "noark5")
            self.assertEqual(plans[1].output_dir, job.work_operations / "arkade5_v2.13.1" / "pronom")
            self.assertNotIn("sip", str(plans[0].output_dir.relative_to(job.work_operations)))
            self.assertNotIn("JOB-001", str(plans[0].output_dir.relative_to(job.work_operations)))
            self.assertEqual(plans[1].args[plans[1].args.index("-F") + 1], "filformatinfo")

    def test_dwm_evidence_follows_app_work_subfolder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / "Arkivverket.Arkade.CLI.exe"
            exe.write_text("placeholder", encoding="utf-8")
            job = self._job(root)
            fake_status = SimpleNamespace(ok=True, version="2.13.1", message="OK")
            settings = {
                "arkade5_cli_path": str(exe),
                "app_work_subfolder": "dwm",
            }
            with patch("noark5_workflow.external_tools.arkade5_jobs.inspect_arkade5_cli", return_value=fake_status):
                plan = build_arkade5_plan(settings, [job], [ARKADE5_NOARK5])[0]

            fake_result = SimpleNamespace(ok=True, launch_error="", timed_out=False, exit_code=0)
            with patch("noark5_workflow.external_tools.arkade5_jobs.run_external_cli", return_value=fake_result) as runner:
                summary = run_arkade5_plan(settings, [plan])

            self.assertEqual(summary.succeeded, 1)
            request = runner.call_args.args[0]
            expected = (
                job.work_operations / "dwm" / "external_runs" / "arkade5"
                / plan.job_id / plan.operation / plan.run_id
            )
            self.assertEqual(request.stdout_path.parent, expected)
            self.assertEqual(request.stderr_path.parent, expected)
            self.assertEqual(request.manifest_path.parent, expected)
            self.assertEqual(request.stdout_path.name, "stdout.txt")
            self.assertEqual(request.stderr_path.name, "stderr.txt")
            self.assertEqual(request.manifest_path.name, "manifest.json")
            self.assertEqual(plan.output_dir, job.work_operations / "arkade5_v2.13.1" / "noark5")


    def test_setup_exposes_output_subfolder_setting(self):
        settings = (ROOT / "settings.py").read_text(encoding="utf-8")
        dialog = (ROOT / "gui" / "settings_dialog_a26_8.py").read_text(encoding="utf-8")
        self.assertIn('"arkade5_output_subfolder": "arkade5_<ver>"', settings)
        self.assertIn("Arkade 5 output-undermappe", dialog)
        self.assertIn("arkade5_<ver>", dialog)
        self.assertIn('updated["arkade5_output_subfolder"]', dialog)

    def test_runtime_and_version_are_a268(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        runtime = (ROOT / "gui" / "persistent_app_a26_8.py").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a26_8 import run_gui", main)
        self.assertIn("class WorkflowApp(A26_7WorkflowApp)", runtime)
        self.assertRegex(version, r'VERSION\s*=\s*"0\.1\.6-a26(?:\.(?:8|9|[1-9]\d+))?"')


if __name__ == "__main__":
    unittest.main()
