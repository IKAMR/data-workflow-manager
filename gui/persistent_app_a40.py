from __future__ import annotations

import webbrowser
from pathlib import Path

from app.noark5_validation_overview import (
    build_validation_overview,
    latest_validation_overview,
    write_validation_overview,
)
from version import VERSION

from . import theme
from .jobs_window_a26 import A26JobsWindow
from .persistent_app_a39 import WorkflowApp as A39WorkflowApp


class WorkflowApp(A39WorkflowApp):
    """v0.1.4-a8: operational Noark 5 validation overview for real batches."""

    def _latest_validation_overview_path(self) -> Path | None:
        return latest_validation_overview(self.settings)

    def _has_validation_overview(self) -> bool:
        return self._latest_validation_overview_path() is not None

    def _open_validation_overview(self) -> None:
        path = self._latest_validation_overview_path()
        if path is None:
            self.status_bar.set_status("Ingen Noark 5 kontrolloversikt er generert ennå")
            return
        webbrowser.open(path.resolve().as_uri())
        self.status_bar.set_status(f"Åpnet kontrolloversikt: {path.name}")

    def _write_run_validation_overview(self, overview) -> None:
        run_id = str(getattr(overview, "run_id", "") or "")
        if not run_id:
            return

        jobs = self.jobs.jobs()
        if not jobs:
            return

        # Only produce this Noark 5-specific overview when the run actually
        # contains Noark 5 jobs. Other future profiles remain unaffected.
        if not any(
            str(getattr(job, "profile_id", "") or "").casefold() == "noark5"
            for job in jobs
        ):
            return

        model = build_validation_overview(
            jobs,
            run_id=run_id,
            job_list_path=self.job_list_path,
            app_version=VERSION,
        )
        files = write_validation_overview(self.settings, model)

        self.log_panel.append(
            f"NOARK 5 KONTROLLOVERSIKT: {files.html_path}"
        )
        self.status_bar.set_status(
            f"Kontrolloversikt generert: {files.html_path.name}"
        )

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.jobs_window.refresh()
            except Exception:
                pass

    def _new_run_log(self, run_type: str, planned_jobs: int | None = None):
        overview = super()._new_run_log(
            run_type,
            planned_jobs=planned_jobs,
        )
        original_finish = overview.finish
        generated = {"done": False}

        def finish_with_validation(status: str = "FERDIG"):
            path = original_finish(status)
            if not generated["done"]:
                generated["done"] = True
                try:
                    self.after(
                        0,
                        lambda ov=overview: self._write_run_validation_overview(ov),
                    )
                except Exception:
                    pass
            return path

        overview.finish = finish_with_validation
        return overview

    def _open_jobs(self) -> None:
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.focus()
            self.jobs_window.lift()
            self.jobs_window.refresh()
            self.jobs_window._refresh_output_rule_preview()
            return

        self.jobs_window = A26JobsWindow(
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


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
