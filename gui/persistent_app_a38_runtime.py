from __future__ import annotations

from tkinter import messagebox

from noark5_workflow.core.job import JobStatus
from version import APP_NAME

from .persistent_app_a37_runtime import WorkflowApp as A37WorkflowApp
from .jobs_window_a38 import A38JobsWindow


class WorkflowApp(A37WorkflowApp):
    """v0.1.6-a38: narrow fixes on top of the proven a37 batch runtime.

    Important: this layer does NOT implement a second batch worker.
    Start valgte / Start klare / Start alle continue to use the inherited a37
    and historical batch execution paths.
    """

    def __init__(self) -> None:
        self._a38_start_action = ""
        super().__init__()

    def _open_jobs(self) -> None:
        """Open/reuse Jobbliste while keeping Åpne available during batch."""
        self._capture_job_operation_params(self.current_job)

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    if isinstance(self.jobs_window, A38JobsWindow):
                        self.jobs_window.deiconify()
                        self.jobs_window.refresh()
                        self.jobs_window.lift()
                        self.jobs_window.focus_force()
                        return
                    self.jobs_window.destroy()
            except Exception:
                pass
            self.jobs_window = None

        self.jobs_window = A38JobsWindow(
            self,
            self.jobs,
            self._open_job,
            self._create_job,
            self._start_all_jobs,
            on_start_selected=self._start_selected_jobs,
            on_stop=self._stop_batch,
            on_new_list=self._new_job_list,
            on_open_list=self._open_job_list_dialog,
            on_save_list=self._save_job_list,
            on_save_list_as=self._save_job_list_as,
            get_list_path=lambda: self.job_list_path,
            get_active_job_id=(
                lambda: self.current_job.job_id if self.current_job else None
            ),
            get_output_subfolder_rule=self._get_output_subfolder_rule,
            set_output_subfolder_rule=self._set_output_subfolder_rule,
            get_batch_execution_config=self._get_batch_execution_config,
            set_batch_execution_config=self._set_batch_execution_config,
            reset_job_execution=self._reset_job_execution,
            get_app_work_subfolder=self._get_app_work_subfolder,
            open_validation_overview=self._open_validation_overview,
            has_validation_overview=self._has_validation_overview,
            on_extraction_discovery=self._a242_apply_discovery,
            on_fill_storage_suggestions=self._a246_fill_storage_suggestions,
            on_discover_arkade5_results=self._a251_discover_arkade5_results,
            on_run_arkade5=self._a266_open_arkade5_run,
            on_apply_standard=self._a37_apply_standard,
            on_apply_workflow=self._a37_apply_workflow,
        )
        self.jobs_window.lift()
        self.jobs_window.focus_force()

    def _a38_call_with_start_action(self, label: str, callback):
        previous = self._a38_start_action
        self._a38_start_action = label
        try:
            return callback()
        finally:
            self._a38_start_action = previous

    def _eligible_batch_jobs(self, jobs):
        """Return jobs the established batch engine may execute.

        Interrupted jobs are represented as SKIPPED by JobRunner.  When such a
        job is explicitly supplied by Start valgte / Start alle, make it READY
        again without resetting its execution cursor so JobRunner can resume.
        """
        runnable = []
        for job in jobs:
            if not job.workflow_ids:
                continue
            if job.status == JobStatus.SKIPPED:
                job.status = JobStatus.READY
                job.message = "Avbrutt tidligere - klar for fortsettelse"
            if job.status in {
                JobStatus.READY,
                JobStatus.WAITING,
                JobStatus.FAILED,
            }:
                runnable.append(job)
        return tuple(runnable)

    def _start_selected_jobs(self) -> None:
        # Keep the a37/a36 implementation exactly: checkbox selection is only a
        # filter into the existing batch engine.
        return self._a38_call_with_start_action(
            "Start valgte",
            super()._start_selected_jobs,
        )

    def _start_ready_jobs(self) -> None:
        return self._a38_call_with_start_action(
            "Start klare",
            super()._start_ready_jobs,
        )

    def _start_all_jobs(self) -> None:
        return self._a38_call_with_start_action(
            "Start alle",
            super()._start_all_jobs,
        )

    def _a38_refresh_execution_ui(self, job) -> None:
        """Refresh live execution state without writing heartbeat noise."""
        if self.current_job is job:
            try:
                self.workflow_panel.refresh()
            except Exception:
                pass
            try:
                self._refresh_active_job_label()
            except Exception:
                pass

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.jobs_window.schedule_refresh()
            except Exception:
                pass

    def _execute_job(self, job, *, batch_mode: bool) -> bool:
        """Use the established JobRunner without 30-second log heartbeats.

        The a36 heartbeat wrote one KJØRER line every 30 seconds and could keep
        displaying the initial Arkade "starter" text for hours.  a38 keeps
        meaningful operation/log output from JobRunner and refreshes GUI state
        as each operation advances instead.
        """
        apply_effective = getattr(self, "_apply_effective_work_operations", None)
        if callable(apply_effective):
            apply_effective(job)

        cancelled = (
            (lambda: self.batch_cancel_requested)
            if batch_mode else
            (lambda: self.cancel_requested)
        )

        def log(message: str) -> None:
            self._job_log(job, str(message or ""))

        def progress(value: float, message: str) -> None:
            self._progress_callback_for_job(job, value, message)
            try:
                self.after(0, lambda j=job: self._a38_refresh_execution_ui(j))
            except Exception:
                pass

        def state(updated) -> None:
            self._persist_execution_state(updated)
            try:
                self.after(
                    0,
                    lambda j=updated: self._a38_refresh_execution_ui(j),
                )
            except Exception:
                pass

        try:
            outcome = self.job_runner.run(
                job,
                progress_cb=progress,
                log_cb=log,
                cancelled_cb=cancelled,
                state_cb=state,
            )
            return bool(outcome.ok)
        finally:
            self._persist_execution_state(job)
            try:
                self.after(0, lambda j=job: self._a38_refresh_execution_ui(j))
            except Exception:
                pass

    def _confirm_rerun(self, jobs) -> bool:
        """Preserve the detailed rerun plan but identify the clicked start action."""
        previous = [
            job for job in jobs
            if job.status in {
                JobStatus.OK,
                JobStatus.FAILED,
                JobStatus.SKIPPED,
            }
            or job.status == JobStatus.WAITING
            or (
                job.status == JobStatus.READY
                and 0 < int(job.next_operation_index or 0) < len(job.workflow_ids)
            )
            or job.message == "Konfigurasjon endret - klar for ny kjøring"
        ]
        if not previous:
            return True

        shown = previous[:6]
        sections = [self._rerun_context_for_job(job) for job in shown]
        if len(previous) > len(shown):
            sections.append(f"... og {len(previous) - len(shown)} jobb(er) til")

        action = self._a38_start_action or "Kjøring"
        message = (
            f"{action} – følgende kjøring er planlagt:\n\n"
            + "\n\n".join(sections)
            + "\n\nTidligere resultatmapper slettes ikke. "
              "Den nye kjøringen dokumenteres som en ny hendelse.\n\n"
              "Fortsette?"
        )
        parent = self.jobs_window if self.jobs_window is not None else self
        return messagebox.askyesno(APP_NAME, message, parent=parent)
