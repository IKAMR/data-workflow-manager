from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest.mock import patch

from noark5_workflow.core.job import Job
from noark5_workflow.external_evidence.arkade5_discovery import Arkade5Candidate
from noark5_workflow.job_batch_actions import discover_arkade5_results_for_jobs


class A251ArkadeBatchDiscoveryTests(unittest.TestCase):
    def test_selected_jobs_are_discovered_independently(self):
        jobs = [
            Job("JOB-001", source_root=Path("C:/A"), work_root=Path("C:/A")),
            Job("JOB-002", source_root=Path("C:/B"), work_root=Path("C:/B")),
        ]
        candidate = Arkade5Candidate(
            path=Path("C:/A/repository_operations/arkade5_v2.13.1/report.json"),
            test_date="2026-09-01",
            tests_run=10,
            errors=1,
            warnings=2,
            sha256="abc",
        )
        with patch(
            "noark5_workflow.job_batch_actions.discover_arkade5_reports_in_roots",
            side_effect=[[candidate], []],
        ) as discover:
            result = discover_arkade5_results_for_jobs(jobs)

        self.assertEqual(discover.call_count, 2)
        self.assertEqual(result.selected_jobs, 2)
        self.assertEqual(result.jobs_with_results, 1)
        self.assertEqual(result.reports_found, 1)
        self.assertEqual(result.jobs_without_results, 1)
        self.assertEqual(result.failed_jobs, 0)

    def test_discovery_is_read_only_not_import(self):
        source = Path("noark5_workflow/job_batch_actions.py").read_text(encoding="utf-8")
        self.assertIn("discover_arkade5_reports_in_roots", source)
        self.assertNotIn("import_discovered_arkade5_reports", source)

    def test_job_actions_exposes_arkade_discovery_for_same_selection(self):
        source = Path("gui/job_batch_action_dialog.py").read_text(encoding="utf-8")
        self.assertIn("Finn Arkade 5-resultater", source)
        self.assertIn("_selected()", source)
        self.assertIn("on_discover_arkade5_results", source)

    def test_result_dialog_preserves_review_before_any_import_action(self):
        source = Path("gui/arkade5_batch_discovery_dialog.py").read_text(encoding="utf-8")
        self.assertTrue("Rapporter koblet" in source or "Rapporter funnet" in source)
        self.assertTrue(
            'ctk.BooleanVar(value=True)' in source
            or 'ctk.BooleanVar(value=not imported)' in source
        )
        self.assertTrue(
            "Ingen Arkade 5-resultater er importert" in source
            or 'text="Importer valgte"' in source
            or 'text="Importer nye valgte"' in source
        )

    def test_runtime_activates_a251(self):
        main = Path("main.py").read_text(encoding="utf-8")
        version = Path("version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a25_1 import run_gui", main)
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a25(?:\.(\d+))?"', version)
        self.assertIsNotNone(match)
        increment = int(match.group(1) or 0)
        self.assertTrue(match.group(1) is None or int(match.group(1)) >= 1)


if __name__ == "__main__":
    unittest.main()
