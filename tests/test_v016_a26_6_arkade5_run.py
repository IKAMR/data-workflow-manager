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
    run_arkade5_plan,
)

ROOT = Path(__file__).resolve().parents[1]


class V016A266Arkade5RunTests(unittest.TestCase):
    def _job(self, root: Path):
        source = root / "source" / "avleveringspakke"
        source.mkdir(parents=True)
        work = root / "repository_operations"
        work.mkdir()
        return SimpleNamespace(
            job_id="JOB-001",
            name="mei-2023-11-28_09-48-45-000787",
            active_extraction_root=source,
            work_operations=work,
        )

    def test_plan_has_separate_noark_and_pronom_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / "Arkivverket.Arkade.CLI.exe"
            exe.write_text("placeholder", encoding="utf-8")
            job = self._job(root)
            fake_status = SimpleNamespace(ok=True, version="2.13.1", message="OK")
            with patch("noark5_workflow.external_tools.arkade5_jobs.inspect_arkade5_cli", return_value=fake_status):
                plans = build_arkade5_plan(
                    {"arkade5_cli_path": str(exe), "temp_dir": str(root / "temp")},
                    [job],
                    [ARKADE5_NOARK5, ARKADE5_PRONOM],
                )
            self.assertEqual(len(plans), 2)
            noark, pronom = plans
            self.assertEqual(noark.args[0], "test")
            self.assertIn("-a", noark.args)
            self.assertIn("-p", noark.args)
            self.assertIn("Noark5", noark.args)
            self.assertEqual(pronom.args[0], "analyse")
            self.assertIn("-f", pronom.args)
            self.assertIn("-F", pronom.args)
            self.assertNotEqual(noark.output_dir, pronom.output_dir)
            self.assertIn("arkade5_v2.13.1", str(noark.output_dir))

    def test_runner_writes_separate_process_evidence_paths(self):
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
                plans = build_arkade5_plan(settings, [job], [ARKADE5_NOARK5])

            fake_result = SimpleNamespace(ok=True, launch_error="", timed_out=False, exit_code=0)
            with patch("noark5_workflow.external_tools.arkade5_jobs.run_external_cli", return_value=fake_result) as runner:
                summary = run_arkade5_plan(settings, plans)

            self.assertEqual(summary.succeeded, 1)
            request = runner.call_args.args[0]

            run_dir = request.stdout_path.parent
            self.assertTrue(run_dir.name.startswith("JOB-001-noark5_test-"))
            self.assertEqual(run_dir.parent.name, "noark5_test")
            self.assertEqual(run_dir.parent.parent.name, "JOB-001")
            self.assertEqual(run_dir.parent.parent.parent.name, "arkade5")
            self.assertEqual(run_dir.parent.parent.parent.parent.name, "external_runs")
            self.assertEqual(run_dir.parent.parent.parent.parent.parent.name, "dwm")

            self.assertEqual(request.stdout_path.name, "stdout.txt")
            self.assertEqual(request.stderr_path.name, "stderr.txt")
            self.assertEqual(request.manifest_path.name, "manifest.json")
            self.assertEqual(request.stdout_path.parent, request.stderr_path.parent)
            self.assertEqual(request.stdout_path.parent, request.manifest_path.parent)
            self.assertEqual(request.job_id, "JOB-001")

    def test_gui_exposes_run_action_and_both_operation_choices(self):
        action = (ROOT / "gui" / "job_batch_action_dialog.py").read_text(encoding="utf-8")
        dialog = (ROOT / "gui" / "arkade5_run_dialog.py").read_text(encoding="utf-8")
        self.assertIn('text="Kjør Arkade 5…"', action)
        self.assertIn('text="Noark 5-test"', dialog)
        self.assertIn('text="PRONOM-analyse (Siegfried)"', dialog)
        self.assertIn('text="Kjør valgte"', dialog)

    def test_runtime_activates_a266(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        runtime = (ROOT / "gui" / "persistent_app_a26_6.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a26_6 import run_gui", main)
        self.assertIn("class WorkflowApp(A26_3WorkflowApp)", runtime)
        self.assertIn("run_arkade5_plan", runtime)

    def test_version_is_a266(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertRegex(version, r'VERSION\s*=\s*"0\.1\.6-a(?:(?:26|2[7-9]|[3-9]\d|[1-9]\d{2,})(?:\.\d+)?)"')


if __name__ == "__main__":
    unittest.main()
