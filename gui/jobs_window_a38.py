from __future__ import annotations

from noark5_workflow.core.job import JobStatus
from .jobs_window_a35 import A35JobsWindow


class A38JobsWindow(A35JobsWindow):
    """a38: safe live Jobbliste behaviour during batch execution."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Completed jobs are not selected by default.  Other states remain
        # selected so ready/interrupted work is visible to the operator.
        self._selected_job_ids = {
            job.job_id
            for job in self.batch.jobs()
            if job.status != JobStatus.OK
        }
        self._invalidate_selection_render()
        self.refresh()

    def _update_row_view(
        self,
        row,
        job,
        *,
        active,
        can_move_up,
        can_move_down,
    ) -> None:
        super()._update_row_view(
            row,
            job,
            active=active,
            can_move_up=can_move_up,
            can_move_down=can_move_down,
        )
        # Viewing a job is safe while a batch is active.  Editing, deleting,
        # reordering and mapper/workflow changes remain disabled upstream.
        view = self._row_views.get(job.job_id)
        if view is not None and "open" in view:
            view["open"].configure(state="normal")
