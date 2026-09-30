from __future__ import annotations

from tkinter import messagebox

from noark5_workflow.job_batch_actions import fill_missing_storage_suggestions
from version import APP_NAME
from . import theme
from .jobs_window_a31 import A31JobsWindow
from .persistent_app_a24_4 import WorkflowApp as A24_4WorkflowApp


class WorkflowApp(A24_4WorkflowApp):
    """v0.1.6-a24.6: reusable batch actions for all or selected jobs."""

    def _open_jobs(self) -> None:
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    if not isinstance(self.jobs_window, A31JobsWindow):
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

        self.jobs_window = A31JobsWindow(
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
            on_extraction_discovery=self._a242_apply_discovery,
            on_fill_storage_suggestions=self._a246_fill_storage_suggestions,
        )

    def _a246_fill_storage_suggestions(self, jobs) -> None:
        selected = tuple(jobs)
        if not selected:
            return

        layout_id = str(
            self.settings.get("storage_layout_profile", "ikamr_standard")
            or "none"
        )
        result = fill_missing_storage_suggestions(
            selected,
            layout_id=layout_id,
        )

        if self.job_list_path is not None:
            self._write_job_list(self.job_list_path)

        if self.jobs_window is not None:
            try:
                self.jobs_window.refresh()
                self.jobs_window._refresh_output_rule_preview()
            except Exception:
                pass

        if self.current_job in selected:
            try:
                self._refresh_active_job_label()
            except Exception:
                pass

        try:
            self.status_bar.set_status(
                f"Mappeforslag: {result.filled_fields} felt i "
                f"{result.changed_jobs} av {result.selected_jobs} jobber"
            )
        except Exception:
            pass

        messagebox.showinfo(
            APP_NAME,
            "Mappeforslag er behandlet.\n\n"
            f"Valgte jobber: {result.selected_jobs}\n"
            f"Jobber endret: {result.changed_jobs}\n"
            f"Tomme felt fylt: {result.filled_fields}\n"
            f"Uten beregnbare forslag: {result.jobs_without_suggestions}\n\n"
            "Eksisterende mappevalg ble ikke overskrevet.",
            parent=self.jobs_window,
        )


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
