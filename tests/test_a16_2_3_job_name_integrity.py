from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from noark5_workflow.core.job import Job
from gui.persistent_app_a28 import WorkflowApp


class A1623JobNameIntegrityTests(unittest.TestCase):
    def _app(self):
        app = object.__new__(WorkflowApp)
        app.settings = {"storage_layout_profile": "ikamr_standard"}
        app.jobs = SimpleNamespace()
        return app

    def test_generated_noark_name_is_recognised(self):
        self.assertTrue(
            WorkflowApp._looks_like_generated_noark_name(
                "1525_004_E-1525-2025-0001",
                "JOB-001",
            )
        )
        self.assertTrue(
            WorkflowApp._looks_like_generated_noark_name("content", "JOB-004")
        )
        self.assertFalse(
            WorkflowApp._looks_like_generated_noark_name(
                "Min manuelle testjobb",
                "JOB-001",
            )
        )

    def test_expected_name_comes_from_current_source_package(self):
        app = self._app()
        job = Job(
            "JOB-001",
            source_root=Path(
                r"G:\arkiv-noark5\1543\1543_012_E-Docu-2025-0001_AIC-5"
            ),
            source_extraction=Path(
                r"G:\arkiv-noark5\1543\1543_012_E-Docu-2025-0001_AIC-5"
                r"\content\sip\content"
            ),
            name="1525_004_E-1525-2025-0001",
            profile_id="noark5",
        )
        self.assertEqual(
            "1543_012_E-Docu-2025-0001_AIC-5",
            app._expected_noark_job_name(job),
        )

    def test_repair_changes_stale_generated_name_only(self):
        app = self._app()
        stale = Job(
            "JOB-001",
            source_root=Path(
                r"G:\arkiv-noark5\1543\1543_012_E-Docu-2025-0001_AIC-5"
            ),
            source_extraction=Path(
                r"G:\arkiv-noark5\1543\1543_012_E-Docu-2025-0001_AIC-5"
                r"\content\sip\content"
            ),
            name="1525_004_E-1525-2025-0001",
            profile_id="noark5",
        )
        custom = Job(
            "JOB-002",
            source_root=Path(
                r"G:\arkiv-noark5\1525\1525_005_E-1525-2025-0001"
            ),
            source_extraction=Path(
                r"G:\arkiv-noark5\1525\1525_005_E-1525-2025-0001"
                r"\content\sip\content"
            ),
            name="Kontrolljobb for WebSak",
            profile_id="noark5",
        )
        app.jobs.jobs = lambda: [stale, custom]
        app._job_log = lambda *args, **kwargs: None

        repaired = app._repair_generated_job_names()

        self.assertEqual(
            "1543_012_E-Docu-2025-0001_AIC-5",
            stale.name,
        )
        self.assertEqual("Kontrolljobb for WebSak", custom.name)
        self.assertEqual(1, len(repaired))
        self.assertEqual("JOB-001", repaired[0][0])

    def test_repair_does_not_reset_execution_state(self):
        app = self._app()
        job = Job(
            "JOB-001",
            source_root=Path(
                r"G:\arkiv-noark5\1543\1543_012_E-Docu-2025-0001_AIC-5"
            ),
            source_extraction=Path(
                r"G:\arkiv-noark5\1543\1543_012_E-Docu-2025-0001_AIC-5"
                r"\content\sip\content"
            ),
            name="1525_004_E-1525-2025-0001",
            profile_id="noark5",
            workflow_ids=["one", "two"],
        )
        job.progress = 0.5
        job.next_operation_index = 1
        app.jobs.jobs = lambda: [job]
        app._job_log = lambda *args, **kwargs: None

        app._repair_generated_job_names()

        self.assertEqual(0.5, job.progress)
        self.assertEqual(1, job.next_operation_index)


if __name__ == "__main__":
    unittest.main()
