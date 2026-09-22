from __future__ import annotations

from app.noark5_validation_overview import (
    build_validation_overview,
    write_validation_overview,
)
from version import VERSION

from . import theme
from .jobs_window_a27 import A27JobsWindow
from .persistent_app_a40 import WorkflowApp as A40WorkflowApp


class WorkflowApp(A40WorkflowApp):
    """v0.1.4-a9: RUN-scoped validation overview and report presentation."""

    def _jobs_participating_in_run(self, overview) -> list:
        records = list(getattr(overview, "records", ()) or ())
        job_ids = {
            str(getattr(record, "job_id", "") or "")
            for record in records
            if str(getattr(record, "job_id", "") or "")
        }

        if not job_ids:
            return list(self.jobs.jobs())

        return [
            job for job in self.jobs.jobs()
            if str(getattr(job, "job_id", "") or "") in job_ids
        ]

    def _write_run_validation_overview(self, overview) -> None:
        run_id = str(getattr(overview, "run_id", "") or "")
        if not run_id:
            return

        jobs = self._jobs_participating_in_run(overview)
        if not jobs:
            return

        noark5_jobs = [
            job for job in jobs
            if str(getattr(job, "profile_id", "") or "").casefold() == "noark5"
        ]
        if not noark5_jobs:
            return

        model = build_validation_overview(
            noark5_jobs,
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

    def _open_jobs(self) -> None:
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.focus()
            self.jobs_window.lift()
            self.jobs_window.refresh()
            self.jobs_window._refresh_output_rule_preview()
            return

        self.jobs_window = A27JobsWindow(
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
