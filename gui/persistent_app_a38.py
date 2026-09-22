from __future__ import annotations

from app.workflow_sequences import workflow_sequence_by_id
from app.work_output_layout import (
    AppWorkSubfolderError,
    effective_work_operations,
    validate_layout,
)
from noark5_workflow.core.output_subfolder import OutputSubfolderRuleError
from settings import save_config
from tkinter import messagebox
from noark5_workflow.core.job import JobStatus
from version import APP_NAME

from . import theme
from .jobs_window_a24 import A24JobsWindow
from .persistent_app_a37 import WorkflowApp as A37WorkflowApp
from .settings_dialog_a24 import SettingsDialog


class WorkflowApp(A37WorkflowApp):
    """v0.1.4-a6: Work root -> app root -> optional job subfolder."""

    def _job_has_historical_execution(self, job) -> bool:
        """Return True when an empty workflow cannot reasonably be intentional."""
        status = getattr(job, "status", None)
        if status in {
            JobStatus.OK,
            JobStatus.FAILED,
            JobStatus.SKIPPED,
            JobStatus.WAITING,
        }:
            return True

        if float(getattr(job, "progress", 0.0) or 0.0) > 0.0:
            return True
        if int(getattr(job, "next_operation_index", 0) or 0) > 0:
            return True

        message = str(getattr(job, "message", "") or "").casefold()
        if "workflow fullført" in message or "workflow stoppet" in message:
            return True

        recent = "\n".join(
            str(entry).casefold()
            for entry in list(getattr(job, "log_entries", ()) or ())[-250:]
        )
        return (
            "workflow fullført" in recent
            or "start: metadataoversikt" in recent
            or "start: noark 5" in recent
        )

    def _repair_invalid_empty_noark5_workflow(self, job) -> bool:
        """Repair the known legacy corruption: completed Noark 5 job with [] workflow.

        A fresh/draft job with zero operations is left untouched. Only a Noark 5
        job with evidence of historical execution is repaired.
        """
        if list(getattr(job, "workflow_ids", ()) or ()):
            return False
        if str(getattr(job, "profile_id", "") or "").casefold() != "noark5":
            return False
        if not self._job_has_historical_execution(job):
            return False

        sequence_id = str(
            self.settings.get(
                "noark5_discovery_workflow",
                "noark5_standard",
            )
            or "noark5_standard"
        )
        sequence = workflow_sequence_by_id(sequence_id)
        if sequence is None or sequence.profile_id != "noark5":
            sequence = workflow_sequence_by_id("noark5_standard")

        if sequence is None or not sequence.operation_ids:
            return False

        job.set_workflow(sequence.operation_ids)
        self._job_log(
            job,
            "GJENOPPRETTING: tom lagret Noark 5-workflow ble reparert "
            f"til {sequence.name} ({len(sequence.operation_ids)} operasjoner).",
            show=False,
        )
        return True

    def _repair_invalid_empty_noark5_workflows(self) -> int:
        repaired = 0
        for job in self.jobs.jobs():
            if self._repair_invalid_empty_noark5_workflow(job):
                repaired += 1
        return repaired

    def _capture_job_operation_params(self, job) -> None:
        """Persistence boundary: the Job model is authoritative.

        In the modern runtime, workflow changes are already written to Job by
        the workflow change hooks. Saving a job list must therefore never copy
        a transient/empty GUI workflow back over Job.workflow_ids. This removes
        the remaining path that could persist a successfully executed six-step
        Noark 5 job with workflow_ids=[].
        """
        return

    def _sync_visible_workflow_from_job(self) -> None:
        """Repair a stale workflow panel from the authoritative active Job."""
        job = self.current_job
        if job is None:
            return

        job_ids = list(getattr(job, "workflow_ids", ()) or ())
        panel_ids = list(self.workflow.operation_ids())
        if panel_ids == job_ids:
            return

        self.workflow.clear()
        for operation_id in job_ids:
            self.workflow.add(operation_id)
        self._apply_job_operation_params(job)
        self.workflow_panel.refresh()

    def _refresh_active_job_label(self) -> None:
        """Show workflow state from the Job model, not transient GUI state."""
        job = self.current_job
        if job is None:
            self.active_job_label.configure(
                text="AKTIV JOBB: ingen",
                text_color=theme.TEXT_SUB,
            )
            return

        jobs = self.jobs.jobs()
        try:
            position = next(
                index
                for index, candidate in enumerate(jobs, start=1)
                if candidate is job or candidate.job_id == job.job_id
            )
        except StopIteration:
            position = 0

        count = len(list(getattr(job, "workflow_ids", ()) or ()))
        if count == 0:
            workflow_text = "Workflow: 0 operasjoner - legg til operasjoner"
        elif count == 1:
            workflow_text = "Workflow: 1 operasjon"
        else:
            workflow_text = f"Workflow: {count} operasjoner"

        position_text = (
            f"{position} av {len(jobs)}"
            if position
            else f"? av {len(jobs)}"
        )
        self.active_job_label.configure(
            text=(
                f"AKTIV JOBB: {position_text} | {job.job_id} | "
                f"{job.name} | {workflow_text}"
            ),
            text_color=theme.BLUE,
        )

    def _refresh_job_list_projection(self) -> None:
        """Keep the active job-list path visible in the main status bar."""
        self.status_bar.set_job_list(self.job_list_path)
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.jobs_window.refresh()
            except Exception:
                pass

    def _load_job_list_file(self, path, *, show_error: bool) -> bool:
        loaded = super()._load_job_list_file(path, show_error=show_error)
        if loaded:
            repaired = self._repair_invalid_empty_noark5_workflows()
            if repaired and self.job_list_path is not None:
                # Persist the repaired authoritative Job model immediately so
                # the corruption does not return on the next restart.
                super()._write_job_list(self.job_list_path)
                self.status_bar.set_status(
                    f"Gjenopprettet workflow for {repaired} Noark 5-jobb(er)"
                )

            self._refresh_job_list_projection()
            self._sync_visible_workflow_from_job()
            self._refresh_active_job_label()
        return loaded

    def _write_job_list(self, path) -> bool:
        # Last invariant guard before persistence. This is deliberately narrow:
        # only historically executed Noark 5 jobs with an impossible empty
        # workflow are repaired. Fresh intentional empty jobs remain untouched.
        self._repair_invalid_empty_noark5_workflows()

        written = super()._write_job_list(path)
        if written:
            try:
                self.after(0, self._refresh_job_list_projection)
                self.after(0, self._refresh_active_job_label)
            except Exception:
                pass
        return written

    def _open_job(self, job) -> None:
        repaired = self._repair_invalid_empty_noark5_workflow(job)
        if repaired and self.job_list_path is not None:
            self._write_job_list(self.job_list_path)

        super()._open_job(job)
        self._sync_visible_workflow_from_job()
        self._refresh_active_job_label()

    def _create_job(self, source_root=None):
        """Create a blank job without opening Mapper automatically.

        Mapper is an explicit action in the header/job dialog. Creating a new
        job/job-list should therefore stay quiet and let the user open Mapper
        only when storage roles actually need review or editing.
        """
        job = self.jobs.new_job(None)
        self.current_job = job
        self.workflow.clear()
        self.workflow_panel.refresh()
        self.source_panel.path_var.set("")
        self.source_panel.detect()
        self._refresh_active_job_label()
        self._update_run_button()
        self.status_bar.set_status(
            f"Opprettet {job.job_id} – bruk Mapper ved behov"
        )
        return job

    def _restore_default_workflow_if_empty(self, job) -> tuple[bool, str]:
        """Restore the configured Noark 5 discovery sequence for an empty job.

        This repairs job lists that were saved with zero operations by the
        earlier GUI/workflow synchronization bug. It only acts when the job is
        empty and the job is a Noark 5 job.
        """
        if list(getattr(job, "workflow_ids", ()) or ()):
            return False, ""

        if str(getattr(job, "profile_id", "") or "").casefold() != "noark5":
            return False, ""

        sequence_id = str(
            self.settings.get(
                "noark5_discovery_workflow",
                "noark5_standard",
            )
            or "noark5_standard"
        )
        sequence = workflow_sequence_by_id(sequence_id)
        if sequence is None or sequence.profile_id != "noark5":
            sequence = workflow_sequence_by_id("noark5_standard")

        if sequence is None or not sequence.operation_ids:
            return False, ""

        job.set_workflow(sequence.operation_ids)
        return True, sequence.name

    def _reset_job_execution(self, job) -> tuple[bool, str]:
        restored, sequence_name = self._restore_default_workflow_if_empty(job)
        ok, message = super()._reset_job_execution(job)
        if not ok:
            return ok, message

        if restored:
            if self.job_list_path is not None:
                self._save_job_list()
            return (
                True,
                f"Kjørestatus/cursor er nullstilt. Tom workflow ble "
                f"gjenopprettet som {sequence_name}.",
            )
        return ok, message

    def _empty_workflow_jobs(self, jobs) -> list:
        return [
            job for job in jobs
            if not list(getattr(job, "workflow_ids", ()) or ())
        ]

    def _start_all_jobs(self) -> None:
        repaired = self._repair_invalid_empty_noark5_workflows()
        if repaired and self.job_list_path is not None:
            self._write_job_list(self.job_list_path)

        empty = self._empty_workflow_jobs(self.jobs.jobs())
        if empty:
            shown = ", ".join(job.job_id for job in empty[:8])
            if len(empty) > 8:
                shown += f" … (+{len(empty) - 8})"
            messagebox.showwarning(
                APP_NAME,
                "Batch kan ikke startes fordi følgende jobb(er) har "
                f"0 operasjoner i workflow:\n\n{shown}\n\n"
                "Bruk Nullstill for å gjenopprette standardworkflow på "
                "Noark 5-jobber, eller åpne jobben og velg workflow manuelt.",
            )
            return

        # The batch uses Job.workflow_ids. Keep the visible workflow panel in
        # step with that model before execution, without writing GUI state back.
        self._sync_visible_workflow_from_job()
        self._refresh_active_job_label()
        super()._start_all_jobs()

    def _get_app_work_subfolder(self) -> str:
        return str(
            self.settings.get("app_work_subfolder", "dwm")
            if self.settings.get("app_work_subfolder", "dwm") is not None
            else "dwm"
        ).strip()

    def _apply_effective_work_operations(self, job) -> None:
        rule = str(
            getattr(self.jobs, "output_subfolder_rule", "") or ""
        )
        job._effective_work_operations = effective_work_operations(
            job.work_operations,
            self._get_app_work_subfolder(),
            rule,
            job,
            self._job_position(job),
        )

    def _set_output_subfolder_rule(
        self,
        rule: str,
    ) -> tuple[bool, str]:
        rule = str(rule or "").strip()
        try:
            validate_layout(
                self._get_app_work_subfolder(),
                rule,
                self.jobs.jobs(),
            )
        except (AppWorkSubfolderError, OutputSubfolderRuleError) as exc:
            return False, str(exc)

        # a37 persists the rule and materializes the effective paths. Because
        # _apply_effective_work_operations is overridden above, the materialized
        # path automatically includes the app-owned Work level.
        return super()._set_output_subfolder_rule(rule)

    def _save_settings(self, settings: dict) -> None:
        old_app_root = self._get_app_work_subfolder()
        super()._save_settings(settings)

        new_app_root = self._get_app_work_subfolder()
        if old_app_root != new_app_root:
            for job in self.jobs.jobs():
                self._apply_effective_work_operations(job)

            if self.jobs_window is not None:
                try:
                    if self.jobs_window.winfo_exists():
                        self.jobs_window._refresh_output_rule_preview()
                        self.jobs_window.refresh()
                except Exception:
                    pass

            self.status_bar.set_status(
                "App-undermappe i Work oppdatert: "
                + (new_app_root or "(blank – Work brukes direkte)")
            )

    def _open_settings(self) -> None:
        SettingsDialog(self, self.settings, self._save_settings)

    def _open_jobs(self) -> None:
        self._capture_job_operation_params(self.current_job)
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.focus()
            self.jobs_window.refresh()
            self.jobs_window._refresh_output_rule_preview()
            return

        self.jobs_window = A24JobsWindow(
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
