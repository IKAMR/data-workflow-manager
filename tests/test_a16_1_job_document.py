from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.core.job import Job, JobStatus
from noark5_workflow.core.job_document_a16 import (
    JobDocumentError, job_document_path, load_job_document, new_stable_job_id,
    save_job_document,
)


class A161JobDocumentTests(unittest.TestCase):
    def test_roundtrip_preserves_job_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            stable_id = new_stable_job_id()
            path = job_document_path(Path(tmp), stable_id)
            job = Job(job_id="JOB-001", source_root=Path(tmp) / "source",
                      workflow_ids=["metadata_inventory"],
                      operation_params={"metadata_inventory": {"option": True}},
                      status=JobStatus.OK, progress=1.0, next_operation_index=1,
                      message="Fullfort", log_entries=["testlogg"])
            save_job_document(path, job, stable_id=stable_id)
            loaded = load_job_document(path)
            self.assertEqual(loaded.stable_id, stable_id)
            self.assertEqual(loaded.job.workflow_ids, job.workflow_ids)
            self.assertEqual(loaded.job.operation_params, job.operation_params)
            self.assertEqual(loaded.job.status, JobStatus.OK)
            self.assertEqual(loaded.job.log_entries, ["testlogg"])
            self.assertEqual(loaded.job.job_id, "JOB-001")

    def test_rejects_mismatched_identity_and_invalid_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = new_stable_job_id()
            second = new_stable_job_id()
            path = job_document_path(Path(tmp), first)
            with self.assertRaises(JobDocumentError):
                save_job_document(path, Job("JOB-001"), stable_id=second)
            save_job_document(path, Job("JOB-001"), stable_id=first)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["stable_job_id"] = second
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(JobDocumentError):
                load_job_document(path)

    def test_distinct_jobs_get_distinct_paths(self):
        root = Path("work")
        left, right = new_stable_job_id(), new_stable_job_id()
        self.assertNotEqual(left, right)
        self.assertNotEqual(job_document_path(root, left), job_document_path(root, right))

    def test_existing_n5jobs_is_not_modified(self):
        from noark5_workflow.core.job_store import FORMAT_VERSION
        self.assertEqual(FORMAT_VERSION, 4)


if __name__ == "__main__":
    unittest.main()
