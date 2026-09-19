from __future__ import annotations

import threading
from tkinter import messagebox

from noark5_workflow.core.job import JobStatus
from version import APP_NAME
from . import theme
from .persistent_app_a24 import WorkflowApp as A24WorkflowApp


class WorkflowApp(A24WorkflowApp):
    """a15.8: run only jobs that currently need execution."""

    @staticmethod
    def _job_is_ready_for_batch(job) -> bool:
        if not job.workflow_ids:
            return False
        return job.status in {JobStatus.READY, JobStatus.WAITING}

    def _start_ready_jobs(self) -> None:
        if self.batch_running:
            return

        candidates = [
            job for job in self.jobs.jobs()
            if self._job_is_ready_for_batch(job)
        ]
        if not candidates:
            messagebox.showinfo(
                APP_NAME,
                "Ingen kjørbare jobber.\n\n"
                "«Start klare» kjører jobber med status Klar eller Venter "
                "som har minst én operasjon i workflowen.",
            )
            return

        if not self._validate_unique_outputs(candidates):
            return

        shown = "\n".join(
            f"- {job.job_id}: {job.name}" for job in candidates[:8]
        )
        if len(candidates) > 8:
            shown += f"\n- ... og {len(candidates) - 8} til"

        if not messagebox.askyesno(
            APP_NAME,
            f"Kjøre {len(candidates)} klar(e) jobb(er)?\n\n"
            f"{shown}\n\n"
            "Ferdige jobber blir ikke kjørt på nytt.",
        ):
            return

        self._capture_job_operation_params(self.current_job)
        self.batch_running = True
        self.batch_cancel_requested = False
        self.workflow_panel.run_button.configure(state="disabled")

        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.set_batch_running(True)

        self.log_panel.append(
            f"BATCH START KLARE: {len(candidates)} av {len(self.jobs.jobs())} jobb(er)"
        )

        def worker() -> None:
            for job in candidates:
                if self.batch_cancel_requested:
                    if job.status == JobStatus.READY:
                        job.status = JobStatus.SKIPPED
                        job.message = "Ikke startet - batch avbrutt"
                    continue

                # READY starts normally. WAITING preserves the established
                # checkpoint continuation semantics in _execute_job().
                self._execute_job(job, batch_mode=True)

            counts = self.jobs.counts()
            waiting = counts.get(JobStatus.WAITING, 0)
            summary = (
                f"BATCH KLARE FERDIG: valgt={len(candidates)}, "
                f"totalt={len(self.jobs.jobs())}, "
                f"ferdig={counts[JobStatus.OK]}, venter={waiting}, "
                f"feil={counts[JobStatus.FAILED]}, "
                f"hoppet over={counts[JobStatus.SKIPPED]}"
            )
            self.after(0, lambda s=summary: self.log_panel.append(s))
            self.after(0, lambda s=summary: self.status_bar.set_status(s))
            self.batch_running = False
            self.after(
                0,
                lambda: self.workflow_panel.run_button.configure(state="normal"),
            )
            self.after(0, self._update_run_button)

            if self.jobs_window is not None and self.jobs_window.winfo_exists():
                self.after(
                    0,
                    lambda: self.jobs_window.set_batch_running(False),
                )
                self.after(0, self.jobs_window.refresh)

        threading.Thread(
            target=worker,
            daemon=True,
            name="n5wfman-start-ready",
        ).start()


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
