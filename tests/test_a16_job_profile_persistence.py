"""Regression tests for job-specific extraction profile persistence.

A profile is data, not a source formatting convention.  Verify the actual
serialized documents instead of searching job_store.py for a source fragment.
"""
from pathlib import Path
import json
import tempfile
import unittest

from noark5_workflow.core.job import JobBatch
from noark5_workflow.core.job_store import save_job_list, load_job_list

ROOT = Path(__file__).resolve().parents[1]


class A16JobProfilePersistenceTests(unittest.TestCase):
    def test_profile_id_is_job_specific(self):
        batch = JobBatch()
        first = batch.new_job(None)
        second = batch.new_job(None)
        first.profile_id = "noark5"
        second.profile_id = "siard"
        self.assertEqual("noark5", first.profile_id)
        self.assertEqual("siard", second.profile_id)

    def test_profile_roundtrip_in_job_list(self):
        batch = JobBatch()
        job = batch.new_job(None)
        job.profile_id = "noark5"
        with tempfile.TemporaryDirectory() as tmp:
            path = save_job_list(
                Path(tmp) / "profiles.n5jobs", batch, active_job_id=job.job_id
            )
            loaded = load_job_list(path)
        self.assertEqual("noark5", loaded.batch.jobs()[0].profile_id)

    def test_legacy_job_without_profile_loads_blank(self):
        job = JobBatch().new_job(None)
        self.assertIsNone(job.profile_id)

    def test_profile_selection_updates_active_job(self):
        text = (ROOT / "gui" / "persistent_app_a13.py").read_text(encoding="utf-8")
        self.assertIn("self.current_job.profile_id=profile_id", text)

    def test_open_job_restores_its_profile_before_source(self):
        text = (ROOT / "gui" / "persistent_app_a13.py").read_text(encoding="utf-8")
        start = text.index("def _open_job(self, job: Job)")
        block = text[start:start + 500]
        self.assertIn("self._apply_profile(job.profile_id, persist=False)", block)
        self.assertLess(
            block.index("_apply_profile(job.profile_id"),
            block.index("extraction=job.active_extraction_root"),
        )

    def test_restart_does_not_reset_restored_active_job_profile(self):
        text = (ROOT / "gui" / "persistent_app_a13.py").read_text(encoding="utf-8")
        start = text.index("def __init__(self) -> None:")
        end = text.index("def _build_header", start)
        block = text[start:end]
        self.assertIn("if self.current_job is not None", block)
        self.assertIn(
            "self._apply_profile(self.current_job.profile_id, persist=False)", block
        )
        self.assertNotIn(
            "self.workflow_panel.on_reorder=self._workflow_reordered\n"
            "        self._apply_profile(None, persist=False)", block
        )

    def test_profile_is_serialized(self):
        """Both the legacy full file and v5 index drafts retain profile IDs."""
        batch = JobBatch()
        first = batch.new_job(None)
        second = batch.new_job(None)
        first.profile_id = "noark5"
        second.profile_id = "siard"

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            # Legacy full-file format remains supported by non-a10 callers.
            legacy_path = save_job_list(folder / "legacy.n5jobs", batch)
            legacy_data = json.loads(legacy_path.read_text(encoding="utf-8"))
            self.assertEqual(
                ["noark5", "siard"],
                [entry["profile_id"] for entry in legacy_data["jobs"]],
            )
            self.assertEqual(
                ["noark5", "siard"],
                [job.profile_id for job in load_job_list(legacy_path).batch.jobs()],
            )

            # Work is not yet approved: v5 must keep both jobs as full drafts.
            index_path = save_job_list(
                folder / "index.n5jobs", batch, work_references={}
            )
            index_data = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(5, index_data["format_version"])
            self.assertEqual(["draft", "draft"], [
                entry["entry_type"] for entry in index_data["jobs"]
            ])
            self.assertEqual(
                ["noark5", "siard"],
                [entry["job"]["profile_id"] for entry in index_data["jobs"]],
            )
            self.assertEqual(
                ["noark5", "siard"],
                [job.profile_id for job in load_job_list(index_path).batch.jobs()],
            )


if __name__ == "__main__":
    unittest.main()
