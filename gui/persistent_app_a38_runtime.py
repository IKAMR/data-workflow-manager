from __future__ import annotations

import threading
from tkinter import messagebox

from noark5_workflow.core.job import JobStatus
from version import APP_NAME

from .persistent_app_a37_runtime import WorkflowApp as A37WorkflowApp


class WorkflowApp(A37WorkflowApp):
    """v0.1.6-a38: strict selected-job batch boundary.

    ``Start valgte`` must use exactly the jobs checked in Jobbliste for every
    stage: preflight, rerun confirmation, validation and execution.
    """

    def _start_selected_jobs(self) -> None:
        if self.batch_running:
            return
        if self.jobs_window is None:
            return

        try:
            selected = tuple(self.jobs_window._selected_jobs_for_run())
        except Exception:
            selected = ()

        selected_ids = frozenset(job.job_id for job in selected)
        if not selected_ids:
            messagebox.showwarning(
                APP_NAME,
                "Velg minst én jobb før «Start valgte».",
                parent=self.jobs_window,
            )
            return

        # Preflight only the explicit selection.  This is deliberately separate
        # from the historical Start alle path.
        candidates = self._batch_preflight(
            selected,
            action_label="Start valgte",
        )
        if candidates is None:
            return

        # Hard selection boundary: an inherited preflight is never allowed to
        # expand the requested set.
        candidates = [
            job for job in candidates
            if job.job_id in selected_ids
        ]
        if not candidates:
            messagebox.showinfo(
                APP_NAME,
                "Ingen av de valgte jobbene er kjørbare etter preflight.",
                parent=self.jobs_window,
            )
            return

        if not self._validate_unique_outputs(candidates):
            return

        # The detailed rerun/resume dialog may inspect status/cursor, but it is
        # now given only the checked jobs.  Unchecked completed jobs therefore
        # cannot appear in this confirmation.
        if not self._confirm_rerun(candidates):
            return

        self._capture_job_operation_params(self.current_job)
        self.batch_running = True
        self.batch_cancel_requested = False
        self.cancel_requested = False
        self.workflow_panel.run_button.configure(state="disabled")
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.set_batch_running(True)

        self.log_panel.append(
            f"BATCH START VALGTE: {len(candidates)} jobb(er) | "
            + ", ".join(job.job_id for job in candidates)
        )

        def worker() -> None:
            try:
                for job in candidates:
                    # Last-line safety boundary.  Even if an older inherited
                    # layer were ever to return too many jobs, only the snapshot
                    # selected at button-click time may execute.
                    if job.job_id not in selected_ids:
                        continue

                    if self.batch_cancel_requested:
                        if job.status == JobStatus.READY:
                            job.status = JobStatus.SKIPPED
                            job.message = "Ikke startet - batch avbrutt"
                        continue

                    if (
                        job.status in {
                            JobStatus.OK,
                            JobStatus.FAILED,
                            JobStatus.SKIPPED,
                        }
                        and not self._recoverable_storage_failure(job)
                    ):
                        job.reset_execution("Klar for ny batchkjøring")

                    # Keep the main window synchronized with the job currently
                    # being processed without changing the selected batch set.
                    self.after(0, lambda j=job: self._open_job(j))
                    self._execute_job(job, batch_mode=True)
            finally:
                self._finish_batch_ui(
                    prefix="BATCH VALGTE FERDIG",
                    selected=len(candidates),
                )

        threading.Thread(
            target=worker,
            daemon=True,
            name="dwm-start-selected-a38",
        ).start()


def run_gui() -> None:
    from . import theme

    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
