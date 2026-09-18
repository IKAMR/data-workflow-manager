from pathlib import Path
import tempfile
import unittest

from noark5_workflow.core.job import Job
from noark5_workflow.core.raw_result_store import RawResultStore
from noark5_workflow.core.result_review import ResultDisposition, ResultReviewLedger
from noark5_workflow.core.result_selection import (
    choose_new_as_current,
    current_result,
    keep_previous_current,
    latest_new_result,
    raw_store_path_for_job,
    review_ledger_path_for_job,
)


class A132ResultVersionChoiceTests(unittest.TestCase):
    def _job(self, td: str) -> Job:
        job = Job(job_id="JOB-001")
        job.work_operations = Path(td) / "repository_operations"
        return job

    def _append(self, job: Job, rid: str, ok: bool = True):
        RawResultStore(raw_store_path_for_job(job)).append(
            operation_id="xpath",
            test_id="N5-X",
            definition_version="1",
            ok=ok,
            message="ok" if ok else "fail",
            job_id=job.job_id,
            result_id=rid,
            recorded_at="2026-09-17T20:00:00+02:00",
        )

    def test_legacy_latest_success_is_implicit_current(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            self._append(job, "r1")
            self._append(job, "r2")
            self.assertEqual("r2", current_result(job, "xpath").result_id)

    def test_new_result_detection_uses_result_id_not_position(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            self._append(job, "r1")
            known = {"r1"}
            self._append(job, "r2")
            self.assertEqual("r2", latest_new_result(job, "xpath", known_result_ids=known).result_id)

    def test_promote_new_supersedes_old_without_deleting_history(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            self._append(job, "r1")
            self._append(job, "r2")
            choice = choose_new_as_current(job, "xpath", "r2", actor="taa")
            self.assertEqual("r1", choice.current.result_id)
            ledger = ResultReviewLedger(review_ledger_path_for_job(job))
            self.assertEqual(ResultDisposition.SUPERSEDED, ledger.current_assessment("r1").disposition)
            self.assertEqual(ResultDisposition.ACCEPTED, ledger.current_assessment("r2").disposition)
            self.assertEqual(2, len(ledger.events()))

    def test_keep_previous_marks_candidate_for_review(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            self._append(job, "r1")
            self._append(job, "r2")
            keep_previous_current(job, "xpath", "r2", actor="taa")
            ledger = ResultReviewLedger(review_ledger_path_for_job(job))
            self.assertEqual(ResultDisposition.ACCEPTED, ledger.current_assessment("r1").disposition)
            self.assertEqual(ResultDisposition.REQUIRES_REVIEW, ledger.current_assessment("r2").disposition)
            self.assertEqual("r1", current_result(job, "xpath").result_id)

    def test_review_ledger_lives_beside_raw_results(self):
        with tempfile.TemporaryDirectory() as td:
            job = self._job(td)
            self.assertEqual(
                raw_store_path_for_job(job).parent,
                review_ledger_path_for_job(job).parent,
            )


if __name__ == "__main__":
    unittest.main()
