from __future__ import annotations

import unittest
from pathlib import Path

from gui.persistent_app_a21 import (
    _resequence_job_batch_for_new_list,
    _restore_job_batch_identities,
)
from noark5_workflow.core.job import Job, JobBatch

ROOT = Path(__file__).resolve().parents[1]


class A113SaveAsJobIdentityTests(unittest.TestCase):
    def test_single_job_002_becomes_job_001(self):
        batch = JobBatch()
        batch.add(Job(job_id="JOB-002", name="JOB-002"))

        snapshot = _resequence_job_batch_for_new_list(batch)

        self.assertEqual([job.job_id for job in batch.jobs()], ["JOB-001"])
        self.assertEqual(batch.jobs()[0].name, "JOB-001")
        self.assertEqual(snapshot[0][1], "JOB-002")

    def test_job_order_is_preserved_and_ids_are_dense_from_one(self):
        batch = JobBatch()
        first = Job(job_id="JOB-004", name="Første")
        second = Job(job_id="JOB-002", name="JOB-002")
        batch.add(first)
        batch.add(second)

        _resequence_job_batch_for_new_list(batch)

        self.assertEqual(batch.jobs(), [first, second])
        self.assertEqual([job.job_id for job in batch.jobs()], ["JOB-001", "JOB-002"])
        self.assertEqual(first.name, "Første")
        self.assertEqual(second.name, "JOB-002")

    def test_next_new_job_continues_after_resequenced_copy(self):
        batch = JobBatch()
        batch.add(Job(job_id="JOB-003"))
        batch.add(Job(job_id="JOB-008"))

        _resequence_job_batch_for_new_list(batch)
        created = batch.new_job(None)

        self.assertEqual(created.job_id, "JOB-003")

    def test_identity_snapshot_can_restore_failed_save_as(self):
        batch = JobBatch()
        first = Job(job_id="JOB-002", name="JOB-002")
        second = Job(job_id="JOB-005", name="Egen tittel")
        batch.add(first)
        batch.add(second)

        snapshot = _resequence_job_batch_for_new_list(batch)
        _restore_job_batch_identities(batch, snapshot)

        self.assertEqual([job.job_id for job in batch.jobs()], ["JOB-002", "JOB-005"])
        self.assertEqual(first.name, "JOB-002")
        self.assertEqual(second.name, "Egen tittel")
        self.assertEqual(batch.new_job(None).job_id, "JOB-006")

    def test_runtime_only_resequences_through_new_copy_reset_hook(self):
        text = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        parent = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")

        self.assertIn("def _reset_jobs_for_new_job_list_copy", text)
        self.assertIn("_resequence_job_batch_for_new_list(", text)
        self.assertIn(
            "is_new_copy = old_path is not None and target != old_path",
            parent,
        )
        self.assertIn("if is_new_copy:", parent)

    def test_failed_save_as_restores_job_identities(self):
        text = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        self.assertIn("def _restore_a11_save_as_identities", text)
        self.assertIn("if not written:", text)
        self.assertIn("self._restore_a11_save_as_identities()", text)


if __name__ == "__main__":
    unittest.main()
