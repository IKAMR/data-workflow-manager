from __future__ import annotations

from noark5_workflow.core.job import Job, JobStatus
from .jobs_window_a17 import A17JobsWindow


_RECOVERABLE_STORAGE_PREFIX = "Lagring utilgjengelig - kan fortsette"


class A18JobsWindow(A17JobsWindow):
    """a16.3: batch/recovery visibility in the job overview."""

    @staticmethod
    def _is_ready_to_run(job: Job) -> bool:
        if not job.workflow_ids:
            return False
        if job.status in {JobStatus.READY, JobStatus.WAITING}:
            return True
        return (
            job.status == JobStatus.FAILED
            and str(job.message or "").startswith(_RECOVERABLE_STORAGE_PREFIX)
        )

    def _status_text(self, job: Job) -> str:
        if (
            job.status == JobStatus.FAILED
            and str(job.message or "").startswith(_RECOVERABLE_STORAGE_PREFIX)
        ):
            return "Feil - kan fortsette"
        return super()._status_text(job)

    def _update_row_view(
        self, row: int, job: Job, *,
        active: bool, can_move_up: bool, can_move_down: bool,
    ) -> None:
        super()._update_row_view(
            row,
            job,
            active=active,
            can_move_up=can_move_up,
            can_move_down=can_move_down,
        )
        view = self._row_views.get(job.job_id)
        if view is None:
            return

        # output_root is not the Noark 5 analysis/result role. Showing it as
        # "Utdata" made correctly configured Noark 5 jobs look incomplete.
        if job.profile_id == "noark5":
            view["output"].configure(
                text=f"Arbeid: {job.work_operations or '(ikke valgt)'}"
            )
        else:
            view["output"].configure(
                text=f"Utdata: {job.output_root or '(ikke valgt)'}"
            )
