from __future__ import annotations

from noark5_workflow.core.job import JobStatus
from . import theme
from .persistent_app_a25 import WorkflowApp as A25WorkflowApp
from .workflow_status import operation_status_key


class WorkflowApp(A25WorkflowApp):
    """a15.9: live workflow status icons and clearer operation progress."""

    def __init__(self) -> None:
        super().__init__()

        # Keep the icon provider explicit at the current runtime boundary.
        # Earlier alpha layers introduced the provider, but later runtime
        # composition must not accidentally leave the panel at "not_run".
        self.workflow_panel.status_provider = self._a159_operation_status_key
        self.workflow_panel.refresh()

    def _a159_operation_status_key(self, operation_id: str) -> str:
        stale_ids = ()
        stale_provider = getattr(self, "_stale_operation_ids", None)
        if callable(stale_provider):
            try:
                stale_ids = stale_provider()
            except Exception:
                stale_ids = ()
        return operation_status_key(
            self.current_job,
            operation_id,
            stale_ids,
        )

    def _refresh_active_workflow_status(self, job) -> None:
        """Refresh only the active workflow when runner state changes.

        Jobber has its own in-place refresh.  The workflow list is small, so a
        row rebuild at operation boundaries is acceptable and makes the status
        icons authoritative after start/completion/failure.
        """
        if self.current_job is not job:
            return
        try:
            if self.workflow_panel.winfo_exists():
                self.workflow_panel.refresh()
        except Exception:
            pass

    def _runner_state_changed(self, job) -> None:
        # Preserve all established persistence/jobs-window behaviour.
        super()._runner_state_changed(job)
        self.after(
            0,
            lambda j=job: self._refresh_active_workflow_status(j),
        )

    def _execute_job(self, job, *, batch_mode: bool) -> bool:
        # Refresh immediately so the first operation can show "Kjører".
        self.after(
            0,
            lambda j=job: self._refresh_active_workflow_status(j),
        )
        ok = super()._execute_job(job, batch_mode=batch_mode)
        # Final state (OK/FAILED/WAITING/SKIPPED) must be visible immediately.
        self.after(
            0,
            lambda j=job: self._refresh_active_workflow_status(j),
        )
        return ok

    def _progress_callback_for_job(self, job, value: float, message: str) -> None:
        """Keep existing progress handling and add operation context.

        The operation counter is deliberately separate from the operation's own
        detailed progress message.  For XPath this produces, for example:
          JOB-003 | Operasjon 4/6 | Test 34/57 - F08 / N5.42 - Skjerminger
        rather than implying that the percentage alone describes the inner test
        catalogue.
        """
        super()._progress_callback_for_job(job, value, message)

        workflow_ids = list(getattr(job, "workflow_ids", ()) or ())
        total = len(workflow_ids)
        if total <= 0:
            return

        cursor = max(
            0,
            min(
                int(getattr(job, "next_operation_index", 0) or 0),
                max(0, total - 1),
            ),
        )

        if getattr(job, "status", None) == JobStatus.OK:
            operation_number = total
        else:
            operation_number = cursor + 1

        detail = str(message or "").strip()
        text = (
            f"{job.job_id} | Operasjon {operation_number}/{total}"
            + (f" | {detail}" if detail else "")
        )

        # Progress callbacks run on the worker thread.  Keep Tk access on the
        # GUI thread.
        self.after(
            0,
            lambda value=text: self.status_bar.set_status(value),
        )


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
