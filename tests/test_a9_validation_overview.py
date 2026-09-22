import json
import tempfile
import unittest
from pathlib import Path

from app.noark5_validation_overview import build_validation_overview
from noark5_workflow.core.job import Job, JobStatus


class A9ValidationOverviewTests(unittest.TestCase):
    def _job(self, root: Path) -> Job:
        job = Job(
            "JOB-001",
            source_root=root / "source",
            profile_id="noark5",
            workflow_ids=["x"],
        )
        job.source_extraction = root / "source"
        job.work_operations = root / "work"
        job._effective_work_operations = job.work_operations
        job.status = JobStatus.OK
        return job

    def _report(self, root: Path, run_id: str) -> Path:
        report_dir = (
            root / "work" / "noark5_reports" / "depot_validation"
            / f"JOB-001__{run_id}"
        )
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "artifact_manifest.json").write_text(
            json.dumps({
                "job_id": "JOB-001",
                "run_id": run_id,
                "source_extraction": str(root / "source"),
            }),
            encoding="utf-8",
        )
        return report_dir / "depot_validation_report.json"

    def test_current_run_never_reuses_previous_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = self._job(root)
            old = self._report(root, "RUN-old")
            old.write_text(json.dumps({
                "technical_validation": {
                    "status": "ok",
                    "summary": {"ok": 52, "error": 0},
                    "reconciliation": {"mismatch": 0},
                },
                "deviations": [],
            }), encoding="utf-8")

            model = build_validation_overview(
                [job],
                run_id="RUN-current",
                job_list_path="jobs.n5jobs",
                app_version="0.1.4-a9",
            )
            self.assertEqual(model["jobs"][0]["control_status"], "MANGLER")

    def test_review_case_and_underlying_findings_are_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = self._job(root)
            report = self._report(root, "RUN-current")
            report.write_text(json.dumps({
                "summary": {"archive_part_count": 28},
                "technical_validation": {
                    "status": "ok",
                    "summary": {"ok": 52, "error": 0, "legacy_disabled": 5},
                    "reconciliation": {"mismatch": 0},
                },
                "standard_values": {
                    "summary": {
                        "status_counts": {
                            "additional_observed_values": 8
                        }
                    }
                },
                "deviations": [{
                    "category": "additional_observed_values",
                    "severity": "review",
                    "requires_review": True,
                }],
                "assessment": {"status": "requires_clarification"},
            }), encoding="utf-8")

            model = build_validation_overview(
                [job],
                run_id="RUN-current",
                job_list_path="jobs.n5jobs",
                app_version="0.1.4-a9",
            )
            row = model["jobs"][0]
            self.assertEqual(row["review_cases"], 1)
            self.assertEqual(row["review_findings"], 8)
            self.assertEqual(row["review_points"], 1)
            self.assertEqual(row["archive_part_count"], 28)
            self.assertEqual(model["format_version"], 2)


if __name__ == "__main__":
    unittest.main()
