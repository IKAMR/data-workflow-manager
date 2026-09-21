from __future__ import annotations

from . import theme
from .persistent_app_a28 import WorkflowApp as A28WorkflowApp
from .persistent_app_a31 import WorkflowApp as A31WorkflowApp
from noark5_workflow.core.job import JobStatus


class WorkflowApp(A31WorkflowApp):
    """a16.4.4: remove the pre-resume GUI/persistence blocking point."""

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

        ok = A28WorkflowApp._execute_job(
            self,
            job,
            batch_mode=batch_mode,
        )

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

        return ok


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
