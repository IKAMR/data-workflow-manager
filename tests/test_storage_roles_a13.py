import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.job import Job, JobBatch
from noark5_workflow.core.job_store import FORMAT_VERSION, load_job_list, save_job_list


class StorageRolesA13Tests(unittest.TestCase):
    def test_job_exposes_generic_storage_roles(self):
        job = Job(
            "JOB-001",
            Path("source"),
            source_tar=Path("delivery.tar"),
            source_unzipped=Path("unpacked"),
            source_extraction=Path("extract"),
            work_root=Path("work"),
            work_content=Path("work/content"),
            work_operations=Path("work/ops"),
            archive_root=Path("archive"),
        )
        self.assertEqual(job.active_extraction_root, Path("extract"))
        self.assertEqual(job.storage_roles.work_operations, Path("work/ops"))

    def test_legacy_source_root_remains_active_extraction_fallback(self):
        job = Job("JOB-001", Path("legacy-extract"))
        self.assertEqual(job.active_extraction_root, Path("legacy-extract"))

    def test_current_job_list_roundtrip_persists_storage_roles(self):
        with tempfile.TemporaryDirectory() as temp:
            batch = JobBatch()
            job = batch.new_job(Path("source"))
            job.work_root = Path("work")
            job.work_operations = Path("work/ops")
            job.source_extraction = Path("extract")
            job.archive_root = Path("archive")

            path = save_job_list(Path(temp) / "jobs.n5jobs", batch)
            payload = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(FORMAT_VERSION, 4)
            self.assertEqual(payload["format_version"], FORMAT_VERSION)
            self.assertEqual(
                payload["jobs"][0]["work_operations"],
                str(Path("work/ops")),
            )

            loaded = load_job_list(path).batch.jobs()[0]
            self.assertEqual(loaded.work_operations, Path("work/ops"))
            self.assertEqual(loaded.source_extraction, Path("extract"))
            self.assertEqual(loaded.archive_root, Path("archive"))

    def test_context_keeps_work_and_archive_separate(self):
        ctx = OperationContext(
            Path("source"),
            work_operations=Path("work/ops"),
            archive_root=Path("archive"),
        )
        self.assertEqual(ctx.work_operations, Path("work/ops"))
        self.assertEqual(ctx.archive_root, Path("archive"))
        self.assertIsNone(ctx.output_root)

    def test_legacy_output_becomes_archive_role(self):
        job = Job(
            "JOB-001",
            Path("source"),
            output_root=Path("dias-output"),
        )
        self.assertEqual(job.archive_root, Path("dias-output"))


if __name__ == "__main__":
    unittest.main()
