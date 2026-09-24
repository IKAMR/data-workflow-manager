
from __future__ import annotations

from noark5_workflow.core.job import Job

from . import theme
from .jobs_window_a28 import A28JobsWindow
from .persistent_app_a52 import WorkflowApp as A52WorkflowApp
from .storage_roles_dialog_a11 import StorageRolesDialog


class WorkflowApp(A52WorkflowApp):
    """v0.1.5-a18: hard boundary between old and new job-list GUI state."""

    def _open_jobs(self) -> None:
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    if not isinstance(self.jobs_window, A28JobsWindow):
                        self.jobs_window.destroy()
                        self.jobs_window = None
                    else:
                        self.jobs_window.focus()
                        self.jobs_window.lift()
                        self.jobs_window.refresh()
                        self.jobs_window._refresh_output_rule_preview()
                        return
            except Exception:
                self.jobs_window = None

        self.jobs_window = A28JobsWindow(
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
            open_validation_overview=self._open_validation_overview,
            has_validation_overview=self._has_validation_overview,
        )

    def _mapper_toplevels(self) -> list[StorageRolesDialog]:
        result = []
        try:
            children = list(self.winfo_children())
        except Exception:
            return result
        for child in children:
            try:
                if isinstance(child, StorageRolesDialog) and child.winfo_exists():
                    result.append(child)
            except Exception:
                continue
        return result

    def _close_all_storage_roles_dialogs(self) -> None:
        candidates = []
        tracked = getattr(self, "_storage_roles_dialog", None)
        if tracked is not None:
            candidates.append(tracked)
        for dialog in self._mapper_toplevels():
            if dialog not in candidates:
                candidates.append(dialog)

        for dialog in candidates:
            try:
                if dialog.winfo_exists():
                    dialog.grab_release()
            except Exception:
                pass
            try:
                if dialog.winfo_exists():
                    dialog.destroy()
            except Exception:
                pass
        self._storage_roles_dialog = None

    def _storage_dialog_destroyed(self, event, dialog) -> None:
        if getattr(event, "widget", None) is not dialog:
            return
        if getattr(self, "_storage_roles_dialog", None) is dialog:
            self._storage_roles_dialog = None

    def _show_storage_roles(self, job: Job) -> None:
        existing = getattr(self, "_storage_roles_dialog", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    if getattr(existing, "job", None) is job:
                        existing.focus()
                        existing.lift()
                        return
                    existing.grab_release()
                    existing.destroy()
            except Exception:
                pass
            self._storage_roles_dialog = None

        for dialog in self._mapper_toplevels():
            try:
                if getattr(dialog, "job", None) is job:
                    self._storage_roles_dialog = dialog
                    dialog.focus()
                    dialog.lift()
                    return
                dialog.grab_release()
                dialog.destroy()
            except Exception:
                pass

        dialog = StorageRolesDialog(
            self,
            job,
            lambda values: self._save_storage_roles(job, values),
        )
        self._storage_roles_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._storage_dialog_destroyed(event, d),
            add="+",
        )

    def _new_job_list(self) -> bool:
        self._close_all_storage_roles_dialogs()

        created = super()._new_job_list()
        if not created:
            return False

        job = self.current_job
        if job is not None:
            storage_values = (
                job.source_root,
                job.source_tar,
                job.source_unzipped,
                job.source_extraction,
                job.work_root,
                job.work_content,
                job.work_operations,
                job.archive_root,
            )
            if any(value is not None for value in storage_values):
                raise RuntimeError(
                    "Ny jobbliste opprettet med arvede jobbspesifikke mapperoller"
                )

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.jobs_window.refresh()
            except Exception:
                pass

        self._refresh_effective_work_status()
        return True


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
