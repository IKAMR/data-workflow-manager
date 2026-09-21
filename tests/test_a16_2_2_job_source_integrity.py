from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from noark5_workflow.core.job import Job
from gui.persistent_app_a28 import WorkflowApp


class A1622JobSourceIntegrityTests(unittest.TestCase):
    def _app(self):
        app = object.__new__(WorkflowApp)
        app.settings = {"storage_layout_profile": "ikamr_standard"}
        return app

    def test_different_package_does_not_match_active_job(self):
        app = self._app()
        job = Job(
            "JOB-002",
            source_root=Path(r"G:\arkiv-noark5\1525\1525_004_E-1525-2025-0001"),
            source_extraction=Path(
                r"G:\arkiv-noark5\1525\1525_004_E-1525-2025-0001\content\sip\content"
            ),
            name="1525_004_E-1525-2025-0001",
        )
        selected = Path(
            r"G:\arkiv-noark5\1543\1543_012_E-Docu-2025-0001_AIC-5\content\sip\content"
        )
        self.assertFalse(app._job_matches_source(job, selected))

    def test_same_package_matches_even_when_extraction_level_differs(self):
        app = self._app()
        root = Path(r"G:\arkiv-noark5\1543\1543_012_E-Docu-2025-0001_AIC-5")
        job = Job(
            "JOB-004",
            source_root=root,
            source_extraction=root / "content" / "sip" / "content" / "content",
            name="1543_012_E-Docu-2025-0001_AIC-5",
        )
        selected = root / "content" / "sip" / "content"
        self.assertTrue(app._job_matches_source(job, selected))

    def test_no_rebase_helper_remains(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "gui"
            / "persistent_app_a28.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("_rebase_job_roles_for_source_change", text)
        self.assertNotIn("repository_operations/_test/009", text)

    def test_source_browse_no_longer_unconditionally_assigns(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "gui"
            / "persistent_app_a28.py"
        ).read_text(encoding="utf-8")
        method = text.split("def _source_browse_complete", 1)[1].split(
            "def run_gui", 1
        )[0]
        self.assertNotIn("job.source_extraction = path", method)
        self.assertIn("Eksisterende jobb blir ikke endret", method)


if __name__ == "__main__":
    unittest.main()
