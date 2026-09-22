from __future__ import annotations

from tkinter import messagebox

from app.job_workflow_policy import (
    has_historical_execution,
    normalise_completed_state,
    restore_default_if_empty,
    workflow_health,
)
from version import APP_NAME

from . import theme
from .jobs_window_a25 import A25JobsWindow
from .persistent_app_a38 import WorkflowApp as A38WorkflowApp


class WorkflowApp(A38WorkflowApp):
    """v0.1.4-a7: consolidated authoritative job/workflow state."""

    def _job_has_historical_execution(self, job) -> bool:
        return has_historical_execution(job)

    def _repair_invalid_empty_noark5_workflow(self, job) -> bool:
        restored, sequence_name = restore_default_if_empty(
            job,
            self.settings,
            historical_only=True,
        )
        if restored:
            self._job_log(
                job,
                "GJENOPPRETTING: tom lagret Noark 5-workflow ble reparert "
                f"til {sequence_name} ({len(job.workflow_ids)} operasjoner).",
                show=False,
            )
        normalise_completed_state(job)
        return restored

    def _restore_default_workflow_if_empty(self, job) -> tuple[bool, str]:
        return restore_default_if_empty(
            job,
            self.settings,
            historical_only=False,
        )

    def _create_job(self, source_root=None):
        """Create one explicit blank job and preserve stable ownership."""
        job = super()._create_job(source_root)

        identity_cb = getattr(self, "current_user_identity", None)
        identity = identity_cb() if callable(identity_cb) else None
        if identity:
            job.set_owner_identity(identity)

        if self.job_list_path is not None:
            self._write_job_list(self.job_list_path)
        return job

    def _workflow_preflight(self, jobs, *, action_label: str) -> bool:
        """One shared workflow-state gate before any batch action."""
        repaired = 0
        normalised = 0
        problems = []

        for job in jobs:
            if self._repair_invalid_empty_noark5_workflow(job):
                repaired += 1
            if normalise_completed_state(job):
                normalised += 1

            health = workflow_health(job, self.registry)
            if not health.ok:
                problems.append(health.message)

        if repaired or normalised:
            if self.job_list_path is not None:
                self._write_job_list(self.job_list_path)
            self._sync_visible_workflow_from_job()
            self._refresh_active_job_label()

        if problems:
            shown = "\n".join(f"- {value}" for value in problems[:8])
            if len(problems) > 8:
                shown += f"\n- ... og {len(problems) - 8} problem(er) til"

            messagebox.showwarning(
                APP_NAME,
                f"{action_label} kan ikke starte.\n\n"
                f"{shown}\n\n"
                "Åpne jobben og korriger workflowen, eller bruk Nullstill "
                "på en Noark 5-jobb med manglende standardworkflow.",
            )
            return False

        return True

    def _start_all_jobs(self) -> None:
        jobs = self.jobs.jobs()
        if not self._workflow_preflight(jobs, action_label="Start alle"):
            return
        super()._start_all_jobs()

    def _start_ready_jobs(self) -> None:
        """Apply the same workflow policy before inherited Start klare logic."""
        eligible = [
            job
            for job in self.jobs.jobs()
            if str(getattr(job, "status", "").value if hasattr(getattr(job, "status", None), "value") else getattr(job, "status", ""))
            in {"Klar", "Venter ved kontrollpunkt", "Feil"}
        ]

        # Only validate jobs that could be considered by inherited Start klare.
        # If none match, let the established implementation explain why.
        if eligible and not self._workflow_preflight(
            eligible,
            action_label="Start klare",
        ):
            return

        super()._start_ready_jobs()

    def _open_jobs(self) -> None:
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.focus()
            self.jobs_window.lift()
            self.jobs_window.refresh()
            self.jobs_window._refresh_output_rule_preview()
            return

        self.jobs_window = A25JobsWindow(
            self,
            self.jobs,
            self._open_job,
            self._create_job,
            self._start_all_jobs,
            self._stop_batch,
            self._new_job_list,
            self._open_job_list_dialog,
            self._save_job_list,
            self._save_job_list_as,
            lambda: self.job_list_path,
            lambda: self.current_job.job_id if self.current_job else None,
            get_output_subfolder_rule=self._get_output_subfolder_rule,
            set_output_subfolder_rule=self._set_output_subfolder_rule,
            get_batch_execution_config=self._get_batch_execution_config,
            set_batch_execution_config=self._set_batch_execution_config,
            reset_job_execution=self._reset_job_execution,
            get_app_work_subfolder=self._get_app_work_subfolder,
        )


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
