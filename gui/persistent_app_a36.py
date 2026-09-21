from __future__ import annotations

from tkinter import messagebox

from . import theme
from .persistent_app_a28 import WorkflowApp as A28WorkflowApp
from .persistent_app_a35 import WorkflowApp as A35WorkflowApp
from noark5_workflow.core.job import JobStatus
from version import APP_NAME


class WorkflowApp(A35WorkflowApp):
    """a16.4.6.9: recovery uses READY partial-cursor semantics, not checkpoint WAITING.

    A recoverable storage failure is not a user checkpoint. The earlier recovery
    handoff set WAITING before entering the executor, which routed execution to
    JobRunner.continue_job() and therefore required a checkpoint immediately
    before the cursor. Storage recovery instead keeps the failed-operation cursor
    and enters JobRunner.run() through READY partial-cursor semantics.
    """

    @classmethod
    def _recoverable_storage_failure(cls, job) -> bool:
        if getattr(job, "status", None) != JobStatus.FAILED:
            return False

        message = str(getattr(job, "message", "") or "")
        if message.startswith("Lagring utilgjengelig - kan fortsette"):
            return True
        if cls._looks_like_io_failure(message):
            return True

        entries = list(getattr(job, "log_entries", ()) or ())
        recent = "\n".join(str(entry) for entry in entries[-120:])
        return (
            "GJENOPPRETTING: eldre lagringsfeil klassifisert som" in recent
            or "LAGRINGSFEIL: recovery avbrutt; kan forsøkes igjen" in recent
        )

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

        # Storage recovery is not a checkpoint continuation. READY with a
        # partial cursor is already supported by JobRunner.run() and starts
        # exactly at next_operation_index without checkpoint validation.
        job.status = JobStatus.READY
        job.message = f"Gjenopptar fra operasjon {cursor + 1}"
        job.operation_params = params_before

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

        if saved_jobs_window is not None:
            try:
                if saved_jobs_window.winfo_exists():
                    self.after(0, saved_jobs_window.refresh)
            except Exception:
                pass

        return ok

    def _confirm_rerun(self, jobs) -> bool:
        """Confirm only ordinary reruns; recoverable storage failures continue."""
        previous = [
            job for job in jobs
            if not self._recoverable_storage_failure(job)
        ]
        if not previous:
            return True

        shown = previous[:6]
        sections = [self._rerun_context_for_job(job) for job in shown]
        if len(previous) > len(shown):
            sections.append(f"... og {len(previous) - len(shown)} jobb(er) til")

        message = (
            "Følgende kjøring er planlagt:\n\n"
            + "\n\n".join(sections)
            + "\n\nTidligere resultatmapper slettes ikke. "
              "Den nye kjøringen dokumenteres som en ny hendelse.\n\n"
              "Fortsette?"
        )
        return messagebox.askyesno(APP_NAME, message)


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
