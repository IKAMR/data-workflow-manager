from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noark5_workflow.core.job import Job
from noark5_workflow.external_evidence.arkade5_discovery import Arkade5Candidate
from noark5_workflow.job_batch_actions import (
    Arkade5DiscoveryBatchResult,
    Arkade5DiscoveryJobResult,
    classify_arkade5_discovery_import_state,
)


class A255ArkadeImportStateTests(unittest.TestCase):
    def _candidate(self, path: Path, sha: str) -> Arkade5Candidate:
        return Arkade5Candidate(
            path=path,
            test_date="2026-10-01",
            tests_run=10,
            errors=0,
            warnings=0,
            sha256=sha,
        )

    def _result(self, job: Job, candidates):
        return Arkade5DiscoveryBatchResult(
            selected_jobs=1,
            jobs_with_results=1,
            reports_found=len(candidates),
            jobs_without_results=0,
            failed_jobs=0,
            unmatched_reports=0,
            job_results=(
                Arkade5DiscoveryJobResult(
                    job_id=job.job_id,
                    job_name=job.name or job.job_id,
                    candidates=tuple(candidates),
                ),
            ),
        )

    def test_existing_sha_is_visible_before_import(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = Job("JOB-001", work_operations=root / "repository_operations")
            candidate = self._candidate(root / "report.json", "same")
            result = self._result(job, [candidate])
            existing = [{"import_id": "old", "source": {"sha256": "same"}}]
            with patch(
                "noark5_workflow.job_batch_actions._list_arkade5_imports",
                return_value=existing,
            ):
                states = classify_arkade5_discovery_import_state([job], result)
            self.assertEqual(states[0].status, "already_imported")
            self.assertEqual(states[0].import_id, "old")

    def test_new_sha_is_selected_as_new_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = Job("JOB-001", work_operations=root / "repository_operations")
            candidate = self._candidate(root / "report.json", "new-sha")
            result = self._result(job, [candidate])
            with patch(
                "noark5_workflow.job_batch_actions._list_arkade5_imports",
                return_value=[],
            ):
                states = classify_arkade5_discovery_import_state([job], result)
            self.assertEqual(states[0].status, "new")

    def test_dialog_defaults_only_new_reports_selected_and_labels_state(self):
        source = Path("gui/arkade5_batch_discovery_dialog.py").read_text(encoding="utf-8")
        self.assertIn('text="Alle nye"', source)
        self.assertIn('text="Importer nye valgte"', source)
        self.assertIn('"Allerede importert" if imported else "Ny"', source)
        self.assertIn('ctk.BooleanVar(value=not imported)', source)
        self.assertTrue(
            'state="disabled" if imported else "normal"' in source
            or ('if imported:' in source and 'text="✓"' in source)
        )
        self.assertIn("def _mark_imported", source)

    def test_runtime_refreshes_same_dialog_after_import(self):
        source = Path("gui/persistent_app_a25_5.py").read_text(encoding="utf-8")
        dialog = Path("gui/arkade5_batch_discovery_dialog.py").read_text(encoding="utf-8")
        self.assertIn("classify_arkade5_discovery_import_state", source)
        self.assertIn("return tuple(imported_keys)", source)
        self.assertNotIn("self.destroy()", dialog.split("def _accept_selected", 1)[1])
        self.assertIn("self._mark_imported(imported_keys)", dialog)

    def test_runtime_and_version_are_a255(self):
        main = Path("main.py").read_text(encoding="utf-8")
        version = Path("version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a25_5 import run_gui", main)
        import re
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', version)
        self.assertIsNotNone(match)
        alpha = int(match.group(1))
        increment = int(match.group(2) or 0)
        self.assertTrue(alpha > 25 or (alpha == 25 and increment >= 5))


if __name__ == "__main__":
    unittest.main()
