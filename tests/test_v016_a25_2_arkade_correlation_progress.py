from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noark5_workflow.core.job import Job
from noark5_workflow.external_evidence.arkade5_discovery import Arkade5Candidate
from noark5_workflow.job_batch_actions import discover_arkade5_results_for_jobs


class A252ArkadeCorrelationAndProgressTests(unittest.TestCase):
    def _candidate(self, path: Path, sha: str) -> Arkade5Candidate:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"Summary":{"SystemName":"Test"},"TestsResults":[]}',
            encoding="utf-8",
        )
        return Arkade5Candidate(
            path=path,
            test_date="2026-09-01",
            tests_run=10,
            errors=0,
            warnings=0,
            sha256=sha,
        )

    def test_shared_work_area_is_scanned_once_and_reports_are_correlated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "1502_003_AIC-1"
            work_ops = root / "repository_operations"
            j1_name = "mei-2023-11-28_09-48-45-000787"
            j2_name = "mk_2TB_2023-11-22_16-47-49-000854"
            j1 = Job(
                "JOB-001",
                name=j1_name,
                source_root=root,
                source_extraction=root / "content" / "sip" / "content" / j1_name / "avleveringspakke",
                work_root=root,
                work_operations=work_ops,
            )
            j2 = Job(
                "JOB-002",
                name=j2_name,
                source_root=root,
                source_extraction=root / "content" / "sip" / "content" / j2_name / "avleveringspakke",
                work_root=root,
                work_operations=work_ops,
            )
            c1 = self._candidate(
                work_ops / "arkade5_v2.13.1" / j1_name / "1502_003_mei_testrapport.json",
                "a",
            )
            c2 = self._candidate(
                work_ops / "arkade5_v2.13.1" / j2_name / "1502_003_mei_2TB_testrapport.json",
                "b",
            )

            with patch(
                "noark5_workflow.job_batch_actions.discover_arkade5_reports_in_roots",
                return_value=[c1, c2],
            ) as discover:
                result = discover_arkade5_results_for_jobs([j1, j2])

            self.assertEqual(discover.call_count, 1)
            self.assertEqual(result.reports_found, 2)
            self.assertEqual(result.unmatched_reports, 0)
            self.assertEqual([row.found for row in result.job_results], [1, 1])
            self.assertEqual(result.job_results[0].candidates[0].path, c1.path)
            self.assertEqual(result.job_results[1].candidates[0].path, c2.path)

    def test_ambiguous_report_is_not_repeated_under_every_job(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "AIC"
            work_ops = root / "repository_operations"
            jobs = [
                Job("JOB-001", name="part-a", source_root=root, work_root=root, work_operations=work_ops),
                Job("JOB-002", name="part-b", source_root=root, work_root=root, work_operations=work_ops),
            ]
            candidate = self._candidate(work_ops / "arkade5_v2.13.1" / "unknown" / "report.json", "x")
            with patch(
                "noark5_workflow.job_batch_actions.discover_arkade5_reports_in_roots",
                return_value=[candidate],
            ):
                result = discover_arkade5_results_for_jobs(jobs)

            self.assertEqual(result.reports_found, 0)
            self.assertEqual(result.unmatched_reports, 1)
            self.assertEqual([row.found for row in result.job_results], [0, 0])

    def test_progress_callback_reports_start_search_and_correlation(self):
        job = Job("JOB-001", name="part-a", source_root=Path("C:/A"), work_root=Path("C:/A"))
        messages = []
        with patch(
            "noark5_workflow.job_batch_actions.discover_arkade5_reports_in_roots",
            return_value=[],
        ):
            discover_arkade5_results_for_jobs([job], on_progress=messages.append)
        joined = "\n".join(messages)
        self.assertIn("Forbereder Arkade 5-søk", joined)
        self.assertIn("Søker Arkade 5-resultater", joined)
        self.assertIn("Kobler Arkade 5-resultater", joined)
        self.assertIn("Arkade 5-søk ferdig", joined)

    def test_job_action_dialog_shows_immediate_wait_text(self):
        source = Path("gui/job_batch_action_dialog.py").read_text(encoding="utf-8")
        self.assertIn("Dette kan ta litt tid", source)
        self.assertIn("update_idletasks", source)

    def test_result_dialog_exposes_unmatched_reports(self):
        source = Path("gui/arkade5_batch_discovery_dialog.py").read_text(encoding="utf-8")
        self.assertIn("Ufordelte rapporter", source)
        self.assertIn("kobles entydig", source)

    def test_runtime_activates_a252(self):
        main = Path("main.py").read_text(encoding="utf-8")
        version = Path("version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a25_2 import run_gui", main)
        import re
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a25(?:\.(\d+))?"', version)
        self.assertIsNotNone(match)
        self.assertTrue(match.group(1) is None or int(match.group(1)) >= 2)


if __name__ == "__main__":
    unittest.main()
