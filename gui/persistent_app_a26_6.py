from __future__ import annotations

from . import theme
from .arkade5_run_dialog import Arkade5RunDialog
from .jobs_window_a33 import A33JobsWindow
from .persistent_app_a26_3 import WorkflowApp as A26_3WorkflowApp
from noark5_workflow.external_tools.arkade5_jobs import run_arkade5_plan


class WorkflowApp(A26_3WorkflowApp):
    """v0.1.6-a26.6: run Arkade 5 Noark/PRONOM operations for selected jobs."""

    def _open_jobs(self) -> None:
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    if not isinstance(self.jobs_window, A33JobsWindow):
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

        self.jobs_window = A33JobsWindow(
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
            on_discover_arkade5_results=self._a251_discover_arkade5_results,
            on_run_arkade5=self._a266_open_arkade5_run,
        )

    def _a266_open_arkade5_run(self, jobs) -> None:
        selected = tuple(jobs)
        if not selected:
            return
        dialog = Arkade5RunDialog(
            self.jobs_window or self,
            self.settings,
            selected,
            on_run=self._a266_run_plan,
        )
        dialog.focus()
        dialog.lift()

    def _a266_run_plan(self, plans, on_progress):
        summary = run_arkade5_plan(
            self.settings,
            tuple(plans),
            on_progress=on_progress,
        )
        try:
            self.status_bar.set_status(
                f"Arkade 5: {summary.succeeded} OK, {summary.failed} feil"
            )
        except Exception:
            pass
        return summary


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
