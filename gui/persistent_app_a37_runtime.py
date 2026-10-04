from __future__ import annotations

from tkinter import messagebox

from app.workflow_sequences import workflow_sequence_by_id
from noark5_workflow.core.job import Job
from settings import save_config
from version import APP_NAME

from .jobs_window_a35 import A35JobsWindow
from .persistent_app_a36_runtime import WorkflowApp as A36WorkflowApp


class WorkflowApp(A36WorkflowApp):
    """v0.1.6-a37: stable Jobbliste workflow assignment for batch clients."""

    _SAFE_BATCH_DEFAULT_KEY = "a37_safe_sequential_default_applied"

    def __init__(self) -> None:
        super().__init__()

        # a37 safety migration: earlier releases defaulted to Auto, which can
        # start several client extractions concurrently.  Apply a one-time
        # sequential default.  The user may explicitly choose Auto/Parallell
        # afterwards; the migration marker prevents us from overriding that
        # later choice on the next application start.
        if not bool(self.settings.get(self._SAFE_BATCH_DEFAULT_KEY, False)):
            self.settings["batch_execution_mode"] = "sequential"
            self.settings["batch_max_workers"] = 1
            self.settings[self._SAFE_BATCH_DEFAULT_KEY] = True
            try:
                save_config({
                    "batch_execution_mode": "sequential",
                    "batch_max_workers": 1,
                    self._SAFE_BATCH_DEFAULT_KEY: True,
                })
            except Exception:
                pass

    def _new_run_log(self, run_type: str, planned_jobs: int | None = None):
        """Keep the batch overview log central instead of cloning it per job.

        Single-job runs retain the established mirror behaviour.  For batch
        runs the text sink snapshots this flag at construction, so a temporary
        override is enough while still letting RunOverviewLog populate the
        shared runtime environment on ``self.settings``.
        """
        if str(run_type).casefold() != "batch":
            return super()._new_run_log(run_type, planned_jobs=planned_jobs)

        key = "copy_run_log_to_work_operations"
        had_key = key in self.settings
        previous = self.settings.get(key, True)
        self.settings[key] = False
        try:
            return super()._new_run_log(run_type, planned_jobs=planned_jobs)
        finally:
            if had_key:
                self.settings[key] = previous
            else:
                self.settings.pop(key, None)

    def _open_jobs(self) -> None:
        self._capture_job_operation_params(self.current_job)

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    if isinstance(self.jobs_window, A35JobsWindow):
                        self.jobs_window.deiconify()
                        self.jobs_window.refresh()
                        self.jobs_window.lift()
                        self.jobs_window.focus_force()
                        return
                    self.jobs_window.destroy()
            except Exception:
                pass
            self.jobs_window = None

        self.jobs_window = A35JobsWindow(
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

    def _a37_apply_standard(
        self,
        jobs: tuple[Job, ...],
        empty_only: bool,
    ) -> None:
        targets = tuple(
            job for job in jobs if not empty_only or not job.workflow_ids
        )
        if not targets:
            messagebox.showinfo(
                APP_NAME,
                "Ingen jobber trenger standard workflow.",
                parent=self.jobs_window,
            )
            return

        sequence_id = str(
            self.settings.get("noark5_discovery_workflow", "noark5_standard")
            or "noark5_standard"
        )
        self._a37_apply_workflow(
            targets,
            sequence_id,
            confirm_replace=not empty_only,
        )

    def _a37_apply_workflow(
        self,
        jobs: tuple[Job, ...],
        sequence_id: str,
        *,
        confirm_replace: bool = True,
    ) -> None:
        """Assign one explicit Noark 5 sequence to all selected jobs."""
        sequence = workflow_sequence_by_id(sequence_id, settings=self.settings)
        if sequence is None or sequence.profile_id != "noark5":
            messagebox.showerror(
                APP_NAME,
                "Valgt Noark 5-workflow finnes ikke.",
                parent=self.jobs_window,
            )
            return

        targets = tuple(jobs)
        if not targets:
            return

        changed = [
            job
            for job in targets
            if list(job.workflow_ids) != list(sequence.operation_ids)
        ]
        existing = [job for job in changed if job.workflow_ids]
        if confirm_replace and existing and not messagebox.askyesno(
            APP_NAME,
            f"Erstatte eksisterende workflow på {len(existing)} av "
            f"{len(targets)} valgte jobb(er) med «{sequence.name}»?",
            parent=self.jobs_window,
        ):
            return

        for job in targets:
            changed_for_job = (
                list(job.workflow_ids) != list(sequence.operation_ids)
                or str(getattr(job, "profile_id", "") or "") != "noark5"
            )
            job.profile_id = "noark5"
            job.set_workflow(sequence.operation_ids)
            if changed_for_job:
                job.reset_execution(
                    f"Workflow satt til {sequence.name} - klar for kjøring"
                )

        # The explicit choice becomes the default for subsequently discovered
        # Noark 5 jobs on this installation as well.
        self.settings["noark5_discovery_workflow"] = sequence.sequence_id
        try:
            save_config({"noark5_discovery_workflow": sequence.sequence_id})
        except Exception:
            pass

        if self.current_job in targets:
            self.workflow.clear()
            for operation_id in self.current_job.workflow_ids:
                self.workflow.add(operation_id)
            self.workflow_panel.refresh()
            self._refresh_active_job_label()

        if self.job_list_path is not None:
            self._write_job_list(self.job_list_path)

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.jobs_window.refresh()
            except Exception:
                pass

        self.status_bar.set_status(
            f"{sequence.name} ({len(sequence.operation_ids)} operasjoner) satt på "
            f"{len(targets)} jobb(er)"
        )
