from __future__ import annotations

import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from noark5_workflow.core.joblist_context import JobListContext

ROOT = Path(__file__).resolve().parents[1]


class V016A271JobListContextTests(unittest.TestCase):
    def test_single_job_is_still_a_job_list_context(self):
        job = SimpleNamespace(job_id="JOB-001")
        context = JobListContext.from_runtime_state([job], job, None)
        self.assertEqual(context.job_count, 1)
        self.assertTrue(context.is_single_job)
        self.assertFalse(context.is_saved)
        self.assertEqual(context.active_job_id, "JOB-001")
        self.assertEqual(context.active_position, 1)
        self.assertEqual(context.display_identity, "Ulagret jobbliste")
        self.assertTrue(context.has_consistent_active_job)

    def test_multi_job_context_tracks_active_position(self):
        jobs = [SimpleNamespace(job_id=f"JOB-{number:03d}") for number in range(1, 4)]
        context = JobListContext.from_runtime_state(
            jobs, jobs[1], Path("lists/client-a.json"),
        )
        self.assertEqual(context.job_count, 3)
        self.assertFalse(context.is_single_job)
        self.assertTrue(context.is_saved)
        self.assertEqual(context.active_job_id, "JOB-002")
        self.assertEqual(context.active_position, 2)
        self.assertEqual(context.display_identity, "client-a.json")
        self.assertIs(context.require_consistent(), context)

    def test_foreign_active_job_is_explicitly_inconsistent(self):
        listed = SimpleNamespace(job_id="JOB-001")
        foreign = SimpleNamespace(job_id="JOB-999")
        context = JobListContext.from_runtime_state([listed], foreign, None)
        self.assertFalse(context.has_consistent_active_job)
        self.assertIsNone(context.active_position)
        with self.assertRaisesRegex(ValueError, "tilhører ikke"):
            context.require_consistent()

    def test_empty_context_cannot_be_required_for_execution(self):
        context = JobListContext.from_runtime_state([], None, None)
        self.assertTrue(context.has_consistent_active_job)
        with self.assertRaisesRegex(ValueError, "ingen jobber"):
            context.require_consistent()

    def test_runtime_layer_derives_context_from_existing_authoritative_state(self):
        source = (ROOT / "gui" / "persistent_app_a27_1.py").read_text(encoding="utf-8")
        self.assertIn("self.jobs.jobs()", source)
        self.assertIn("self.current_job", source)
        self.assertIn("self.job_list_path", source)
        self.assertNotIn("self._joblist_context =", source)

    def test_main_activates_a271(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a27_1 import run_gui", main)

    def test_version_is_a271_or_newer_v016_alpha(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.\d+)?"', version)
        self.assertIsNotNone(match, version)
        self.assertGreaterEqual(int(match.group(1)), 27)


if __name__ == "__main__":
    unittest.main()
