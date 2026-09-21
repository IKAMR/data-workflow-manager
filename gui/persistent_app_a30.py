from __future__ import annotations

from noark5_workflow.core.job import JobStatus
from . import theme
from .jobs_window_a19 import A19JobsWindow
from .persistent_app_a29 import WorkflowApp as A29WorkflowApp


_RECOVERABLE_STORAGE_PREFIX = "Lagring utilgjengelig - kan fortsette"
_IO_MARKERS = (
    "[Errno ",
    "[WinError ",
    "Input/output error",
    "I/O error",
    "Invalid argument",
    "The device is not ready",
    "The network name is no longer available",
    "The specified network name is no longer available",
)


class WorkflowApp(A29WorkflowApp):
    """a16.3.1: migrate/recover storage failures from older job lists.

    a16.3 could mark new I/O failures as recoverable, but a failure created in
    a16.2.x remained a plain FAILED job. This layer recognises the historical
    message on load/preflight without resetting workflow parameters or the
    execution cursor.
    """

    @staticmethod
    def _looks_like_io_failure(message: str) -> bool:
        value = str(message or "")
        return any(marker.casefold() in value.casefold() for marker in _IO_MARKERS)

    @classmethod
    def _recoverable_storage_failure(cls, job) -> bool:
        if job.status != JobStatus.FAILED:
            return False
        message = str(job.message or "")
        return (
            message.startswith(_RECOVERABLE_STORAGE_PREFIX)
            or cls._looks_like_io_failure(message)
        )

    def _mark_legacy_storage_failure_recoverable(self, job) -> bool:
        """Add the a16.3 recovery marker without changing cursor/parameters."""
        if job.status != JobStatus.FAILED:
            return False

        message = str(job.message or "")
        if message.startswith(_RECOVERABLE_STORAGE_PREFIX):
            return False
        if not self._looks_like_io_failure(message):
            return False

        job.message = f"{_RECOVERABLE_STORAGE_PREFIX}: {message}"
        try:
            self._job_log(
                job,
                "GJENOPPRETTING: eldre lagringsfeil klassifisert som "
                "«Feil - kan fortsette»; operasjonsposisjon og parametre beholdt",
            )
        except Exception:
            pass
        return True

    def _migrate_legacy_storage_failures(self) -> int:
        changed = 0
        for job in self.jobs.jobs():
            if self._mark_legacy_storage_failure_recoverable(job):
                changed += 1
        return changed

    def _load_job_list_file(self, path, *, show_error: bool) -> bool:
        loaded = super()._load_job_list_file(path, show_error=show_error)
        if not loaded:
            return False

        changed = self._migrate_legacy_storage_failures()
        if changed:
            self.status_bar.set_status(
                f"{changed} eldre lagringsfeil kan nå fortsettes. "
                "Operasjonsposisjon og parametre er beholdt."
            )
            if self.jobs_window is not None:
                try:
                    if self.jobs_window.winfo_exists():
                        self.jobs_window.refresh()
                except Exception:
                    pass
        return True

    def _batch_preflight(self, jobs, *, action_label: str):
        # Also handles a job list that was already open when the app was
        # upgraded from a16.2.x to a16.3.1.
        self._migrate_legacy_storage_failures()
        return super()._batch_preflight(jobs, action_label=action_label)

    def _open_jobs(self) -> None:
        self._capture_job_operation_params(self.current_job)
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.focus()
            self.jobs_window.lift()
            self.jobs_window.refresh()
            return
        self.jobs_window = A19JobsWindow(
            self, self.jobs, self._open_job, self._create_job, self._start_all_jobs,
            self._stop_batch, self._new_job_list, self._open_job_list_dialog,
            self._save_job_list, self._save_job_list_as, lambda: self.job_list_path,
            lambda: self.current_job.job_id if self.current_job else None,
        )


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
