from __future__ import annotations

from noark5_workflow.core.job import JobStatus
from . import theme
from .persistent_app_a28 import WorkflowApp as A28WorkflowApp
from .persistent_app_a32 import WorkflowApp as A32WorkflowApp


class WorkflowApp(A32WorkflowApp):
    """a16.4.5: recovery must not refresh/open jobs while batch lock is active.

    The repeated warning
        "Vent til batch-kjøringen er ferdig eller stopp den først."
    is consistent with the jobs overview being refreshed while batch_running is
    true and its active-row/open callback trying to open a job again.

    During the narrow recovery handoff we therefore detach the jobs window from
    the established executor. The executor can run the job without touching the
    overview. The window is restored afterwards and refreshed once on the Tk
    thread.
    """

    def _execute_job(self, job, *, batch_mode: bool) -> bool:
        if not self._recoverable_storage_failure(job):
            return super()._execute_job(job, batch_mode=batch_mode)

        cursor = int(job.next_operation_index or 0)
        params_before = dict(job.operation_params or {})

        self._job_log(
            job,
            f"GJENOPPTAR: operasjon {cursor + 1} etter lagringsfeil "
            "(cursor og operasjonsparametre beholdes)",
        )

        job.status = JobStatus.WAITING
        job.message = f"Gjenopptar fra operasjon {cursor + 1}"
        job.operation_params = params_before

        # Important: persistent_app._execute_job() refreshes jobs_window at
        # RUNNING and after each operation. During a batch recovery that refresh
        # can feed back into the open-job callback, which is intentionally
        # blocked while batch_running=True and produced the modal warning loop.
        #
        # Detach only the view object. The Job, workflow cursor, params and batch
        # state remain untouched.
        saved_jobs_window = self.jobs_window
        self.jobs_window = None
        try:
            ok = A28WorkflowApp._execute_job(
                self,
                job,
                batch_mode=batch_mode,
            )
        finally:
            self.jobs_window = saved_jobs_window

        if (
            not ok
            and job.status == JobStatus.FAILED
            and self._looks_like_io_failure(job.message)
        ):
            raw = str(job.message or "")
            prefix = "Lagring utilgjengelig - kan fortsette"
            if not raw.startswith(prefix):
                job.message = f"{prefix}: {raw}"
            self._job_log(
                job,
                "LAGRINGSFEIL: recovery avbrutt; kan forsøkes igjen fra "
                "samme feilede operasjon",
            )

        # One safe refresh after the executor has returned. No repeated modal
        # callback can be generated during the actual handoff/execution.
        if saved_jobs_window is not None:
            try:
                if saved_jobs_window.winfo_exists():
                    self.after(0, saved_jobs_window.refresh)
            except Exception:
                pass

        return ok


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
