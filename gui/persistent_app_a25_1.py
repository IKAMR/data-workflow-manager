from __future__ import annotations

from noark5_workflow.job_batch_actions import discover_arkade5_results_for_jobs
from . import theme
from .arkade5_batch_discovery_dialog import Arkade5BatchDiscoveryDialog
from .jobs_window_a32 import A32JobsWindow
from .persistent_app_a24_5 import WorkflowApp as A24_5WorkflowApp


class WorkflowApp(A24_5WorkflowApp):
    """v0.1.6-a25.1: discover existing Arkade 5 results for selected jobs."""

    def _open_jobs(self) -> None:
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    if not isinstance(self.jobs_window, A32JobsWindow):
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

        self.jobs_window = A32JobsWindow(
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
        )

    @staticmethod
    def _a251_configured_roots(settings) -> tuple[str, ...]:
        raw = settings.get("arkade5_report_search_roots", [])
        if isinstance(raw, str):
            return (raw,) if raw.strip() else ()
        if isinstance(raw, (list, tuple)):
            return tuple(str(value) for value in raw if str(value).strip())
        return ()

    def _a251_discover_arkade5_results(self, jobs) -> None:
        selected = tuple(jobs)
        if not selected:
            return

        result = discover_arkade5_results_for_jobs(
            selected,
            configured_roots=self._a251_configured_roots(self.settings),
        )

        try:
            self.status_bar.set_status(
                f"Arkade 5: {result.reports_found} rapporter funnet i "
                f"{result.jobs_with_results} av {result.selected_jobs} jobber"
            )
        except Exception:
            pass

        dialog = Arkade5BatchDiscoveryDialog(self.jobs_window or self, result)
        dialog.focus()
        dialog.lift()


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
