from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noark5_workflow.core.job import Job
from noark5_workflow.external_evidence.arkade5_discovery import Arkade5Candidate
from noark5_workflow.job_batch_actions import import_selected_arkade5_results


class A254ArkadeSelectedImportTests(unittest.TestCase):
    def _candidate(self, path: Path, sha: str = "abc") -> Arkade5Candidate:
        return Arkade5Candidate(
            path=path,
            test_date="2026-10-01",
            tests_run=10,
            errors=0,
            warnings=0,
            sha256=sha,
        )

    def test_selected_report_is_imported_to_correct_job_work_operations(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            j1 = Job("JOB-001", work_operations=root / "job1" / "repository_operations")
            j2 = Job("JOB-002", work_operations=root / "job2" / "repository_operations")
            c = self._candidate(root / "report.json")

            with patch(
                "noark5_workflow.job_batch_actions._list_arkade5_imports",
                return_value=[],
            ), patch(
                "noark5_workflow.job_batch_actions._import_arkade5_report",
                return_value={"import_id": "imp1", "source": {"sha256": "abc"}},
            ) as importer, patch(
                "noark5_workflow.job_batch_actions._attach_arkade5_pronom_evidence",
                return_value=None,
            ):
                result = import_selected_arkade5_results([j1, j2], [("JOB-002", c)])

            self.assertEqual(result.imported, 1)
            self.assertEqual(result.selected_jobs, 1)
            self.assertEqual(importer.call_args.kwargs["work_operations"], j2.work_operations)

    def test_already_imported_sha_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = Job("JOB-001", work_operations=root / "repository_operations")
            c = self._candidate(root / "report.json", "same")
            existing = [{"import_id": "old", "source": {"sha256": "same"}}]
            with patch(
                "noark5_workflow.job_batch_actions._list_arkade5_imports",
                return_value=existing,
            ), patch(
                "noark5_workflow.job_batch_actions._import_arkade5_report"
            ) as importer, patch(
                "noark5_workflow.job_batch_actions._attach_arkade5_pronom_evidence",
                return_value=None,
            ):
                result = import_selected_arkade5_results([job], [(job.job_id, c)])
            self.assertEqual(result.already_imported, 1)
            self.assertEqual(result.imported, 0)
            importer.assert_not_called()

    def test_missing_work_operations_is_reported_not_imported(self):
        job = Job("JOB-001")
        c = self._candidate(Path("report.json"))
        result = import_selected_arkade5_results([job], [(job.job_id, c)])
        self.assertEqual(result.failed, 1)
        self.assertIn("Work - operations", result.item_results[0].error)

    def test_dialog_now_imports_selected(self):
        source = Path("gui/arkade5_batch_discovery_dialog.py").read_text(encoding="utf-8")
        self.assertTrue('text="Importer valgte"' in source or 'text="Importer nye valgte"' in source)
        self.assertIn("bevarer originalrapporten", source)

    def test_runtime_imports_selected_and_activates_a254(self):
        app = Path("gui/persistent_app_a25_4.py").read_text(encoding="utf-8")
        main = Path("main.py").read_text(encoding="utf-8")
        version = Path("version.py").read_text(encoding="utf-8")
        self.assertIn("import_selected_arkade5_results", app)
        self.assertIn("from gui.persistent_app_a25_4 import run_gui", main)
        import re
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', version)
        self.assertIsNotNone(match)
        alpha = int(match.group(1))
        increment = int(match.group(2) or 0)
        self.assertTrue(alpha > 25 or (alpha == 25 and increment >= 4))


if __name__ == "__main__":
    unittest.main()
