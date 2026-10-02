from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from noark5_workflow.external_tools.arkade5_auto_import import import_arkade5_run_outputs
from noark5_workflow.external_tools.arkade5_jobs import (
    ARKADE5_NOARK5,
    ARKADE5_PRONOM,
    Arkade5BatchRunSummary,
    Arkade5JobRun,
    Arkade5PlannedRun,
)

ROOT = Path(__file__).resolve().parents[1]


class V016A269ArkadeAutoImportTests(unittest.TestCase):
    def _plan(self, root: Path, operation: str) -> Arkade5PlannedRun:
        work = root / "repository_operations"
        work.mkdir(exist_ok=True)
        output = work / "arkade5_v2.13.1" / ("noark5" if operation == ARKADE5_NOARK5 else "pronom")
        output.mkdir(parents=True, exist_ok=True)
        return Arkade5PlannedRun(
            job_id="JOB-001",
            job_name="test",
            operation=operation,
            source=root / "source",
            work_operations=work,
            output_dir=output,
            processing_dir=None,
            args=(),
            run_id=f"JOB-001-{operation}-run",
            tool_version="2.13.1",
        )

    def test_auto_import_uses_only_reports_captured_from_exact_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / "new_report.json"
            report.write_text("{}", encoding="utf-8")
            plan = self._plan(root, ARKADE5_NOARK5)
            summary = Arkade5BatchRunSummary((
                Arkade5JobRun(plan=plan, ok=True, generated_reports=(report,)),
            ))
            manifest = {"import_id": "20261001-abcdef", "source": {"sha256": "dummy"}}
            with patch("noark5_workflow.external_tools.arkade5_auto_import._sha256", return_value="abc"), \
                 patch("noark5_workflow.external_tools.arkade5_auto_import.list_arkade5_imports", return_value=[]), \
                 patch("noark5_workflow.external_tools.arkade5_auto_import.import_arkade5_report", return_value=manifest) as importer:
                result = import_arkade5_run_outputs(summary)
            self.assertEqual(result.imported, 1)
            importer.assert_called_once()
            self.assertEqual(importer.call_args.args[0], report)
            self.assertEqual(importer.call_args.kwargs["work_operations"], plan.work_operations / "dwm")
            self.assertEqual(importer.call_args.kwargs["imported_by"]["job_id"], "JOB-001")

    def test_pronom_is_attached_to_same_job_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / "new_report.json"
            report.write_text("{}", encoding="utf-8")
            noark = self._plan(root, ARKADE5_NOARK5)
            pronom = self._plan(root, ARKADE5_PRONOM)
            stats = pronom.output_dir / "filformatinfo-statistikk.csv"
            stats.write_text("Format-ID;Antall\nfmt/18;1\n", encoding="utf-8")
            summary = Arkade5BatchRunSummary((
                Arkade5JobRun(plan=noark, ok=True, generated_reports=(report,)),
                Arkade5JobRun(plan=pronom, ok=True),
            ))
            manifest = {"import_id": "20261001-abcdef", "source": {"sha256": "abc"}}
            with patch("noark5_workflow.external_tools.arkade5_auto_import._sha256", return_value="abc"), \
                 patch("noark5_workflow.external_tools.arkade5_auto_import.list_arkade5_imports", return_value=[]), \
                 patch("noark5_workflow.external_tools.arkade5_auto_import.import_arkade5_report", return_value=manifest), \
                 patch("noark5_workflow.external_tools.arkade5_auto_import.attach_arkade5_pronom_evidence", return_value={"statistics_imported": True, "status": "ok"}) as attach:
                result = import_arkade5_run_outputs(summary)
            self.assertEqual(result.imported, 1)
            self.assertEqual(result.pronom_attached, 1)
            self.assertEqual(attach.call_args.kwargs["import_id"], "20261001-abcdef")
            self.assertEqual(attach.call_args.kwargs["work_operations"], noark.work_operations / "dwm")
            self.assertEqual(Path(attach.call_args.args[0]).parent, pronom.output_dir)

    def test_runtime_and_dialog_expose_automatic_import(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        runtime = (ROOT / "gui" / "persistent_app_a26_9.py").read_text(encoding="utf-8")
        dialog = (ROOT / "gui" / "arkade5_run_dialog.py").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a26_9 import run_gui", main)
        self.assertIn("import_arkade5_run_outputs", runtime)
        self.assertIn("Automatisk import:", dialog)
        self.assertRegex(version, r'VERSION\s*=\s*"0\.1\.6-a(?:(?:26|2[7-9]|[3-9]\d|[1-9]\d{2,})(?:\.\d+)?)"')


if __name__ == "__main__":
    unittest.main()
