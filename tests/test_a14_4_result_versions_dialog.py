from pathlib import Path
import tempfile
import unittest

from noark5_workflow.core.job import Job
from noark5_workflow.core.raw_result_store import RawResultEnvelope, RawResultStore
from noark5_workflow.core.result_review import (
    ResultAssessment,
    ResultDisposition,
    ResultReviewLedger,
)
from noark5_workflow.core.result_selection import review_ledger_path_for_job
from gui.result_versions_dialog import result_version_rows


class A144ResultVersionsTests(unittest.TestCase):
    def _job(self, td: str) -> Job:
        root = Path(td) / "ops"
        return Job("JOB-001", work_operations=root, workflow_ids=["op-x"])

    def _append_raw(self, job: Job, result_id: str, recorded_at: str, ok: bool = True):
        path = Path(job.work_operations) / "wf" / "results" / "raw-results.jsonl"
        store = RawResultStore(path)
        return store.append(
            operation_id="op-x",
            test_id="test-x",
            definition_version="1",
            ok=ok,
            message="test",
            data={},
            warnings=[],
            outputs=[],
            source_root="",
            job_id=job.job_id,
            result_id=result_id,
            recorded_at=recorded_at,
        )

    def test_rows_keep_all_versions_and_mark_explicit_current(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            old = self._append_raw(job, "r1", "2026-09-18T08:00:00+02:00")
            new = self._append_raw(job, "r2", "2026-09-18T08:10:00+02:00")
            ledger = ResultReviewLedger(review_ledger_path_for_job(job))
            ledger.append(ResultAssessment(old.ref, ResultDisposition.SUPERSEDED, superseded_by_result_id="r2"))
            ledger.append(ResultAssessment(new.ref, ResultDisposition.ACCEPTED))
            rows = result_version_rows(job, "op-x")
            self.assertEqual(["r1", "r2"], [r.result_id for r in rows])
            self.assertEqual([False, True], [r.current for r in rows])
            self.assertEqual("superseded", rows[0].assessment)
            self.assertEqual("accepted", rows[1].assessment)

    def test_requires_review_is_visible_without_becoming_current(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            current = self._append_raw(job, "r1", "2026-09-18T08:00:00+02:00")
            candidate = self._append_raw(job, "r2", "2026-09-18T08:10:00+02:00")
            ledger = ResultReviewLedger(review_ledger_path_for_job(job))
            ledger.append(ResultAssessment(current.ref, ResultDisposition.ACCEPTED))
            ledger.append(ResultAssessment(candidate.ref, ResultDisposition.REQUIRES_REVIEW, reason="Alternativ"))
            rows = result_version_rows(job, "op-x")
            self.assertTrue(rows[0].current)
            self.assertFalse(rows[1].current)
            self.assertEqual("requires_review", rows[1].assessment)
            self.assertEqual("Alternativ", rows[1].reason)

    def test_legacy_latest_success_is_implicit_current(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            self._append_raw(job, "r1", "2026-09-18T08:00:00+02:00")
            self._append_raw(job, "r2", "2026-09-18T08:10:00+02:00")
            rows = result_version_rows(job, "op-x")
            self.assertEqual([False, True], [r.current for r in rows])
            self.assertIn("legacy", rows[1].assessment)

    def test_operation_identity_not_workflow_position_drives_history(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            self._append_raw(job, "r1", "2026-09-18T08:00:00+02:00")
            job.workflow_ids = ["other", "op-x"]
            rows = result_version_rows(job, "op-x")
            self.assertEqual(1, len(rows))
            self.assertEqual("r1", rows[0].result_id)

    def test_no_results_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            self.assertEqual([], result_version_rows(job, "op-x"))


if __name__ == "__main__":
    unittest.main()
