import tempfile
import unittest
from pathlib import Path

from app.noark5_validation_overview import (
    build_validation_overview,
    latest_depot_report,
)
from noark5_workflow.core.job import Job, JobStatus


class A8ValidationOverviewTests(unittest.TestCase):
    def test_missing_report_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            job = Job(
                "JOB-001",
                source_root=Path(td) / "source",
                profile_id="noark5",
                workflow_ids=["x"],
            )
            job.work_operations = Path(td) / "work"
            job._effective_work_operations = job.work_operations

            model = build_validation_overview(
                [job],
                run_id="RUN-test",
                job_list_path="jobs.n5jobs",
                app_version="0.1.4-a8",
            )
            self.assertEqual(model["jobs"][0]["control_status"], "MANGLER")

    def test_report_with_review_point_is_vurder(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / "work"
            report_dir = (
                work / "noark5_reports" / "depot_validation" / "JOB-001__RUN-test"
            )
            report_dir.mkdir(parents=True)
            (report_dir / "artifact_manifest.json").write_text(
                '{"job_id":"JOB-001","run_id":"RUN-test","source_extraction":"%s"}'
                % str(root / "source").replace("\\", "\\\\"),
                encoding="utf-8",
            )
            (report_dir / "depot_validation_report.json").write_text(
                """{
  "technical_validation": {
    "status": "ok",
    "summary": {"ok": 52, "error": 0, "legacy_disabled": 5, "other": 0},
    "reconciliation": {"mismatch": 0}
  },
  "deviations": [
    {"severity": "review", "requires_review": true}
  ],
  "assessment": {"status": "requires_clarification"}
}""",
                encoding="utf-8",
            )

            job = Job(
                "JOB-001",
                source_root=root / "source",
                profile_id="noark5",
                workflow_ids=["x"],
            )
            job.source_extraction = root / "source"
            job.work_operations = work
            job._effective_work_operations = work
            job.status = JobStatus.OK

            model = build_validation_overview(
                [job],
                run_id="RUN-test",
                job_list_path="jobs.n5jobs",
                app_version="0.1.4-a8",
            )
            row = model["jobs"][0]
            self.assertEqual(row["control_status"], "VURDER")
            self.assertEqual(row["tests_ok"], 52)
            self.assertEqual(row["review_points"], 1)


if __name__ == "__main__":
    unittest.main()
