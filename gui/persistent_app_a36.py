from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from . import theme
from .jobs_window_a20 import A20JobsWindow
from .persistent_app_a28 import WorkflowApp as A28WorkflowApp
from .persistent_app_a35 import WorkflowApp as A35WorkflowApp
from noark5_workflow.core.batch_runner import BatchRunner
from noark5_workflow.core.job import JobStatus
from noark5_workflow.core.job_runner import JobRunner
from noark5_workflow.core.job_store import load_job_list
from noark5_workflow.core.output_subfolder import (
    OutputSubfolderRuleError,
    effective_work_operations,
    validate_output_subfolder_rule,
)
from version import APP_NAME


class RuleAwareJobRunner(JobRunner):
    """Use a transient effective Work - operations path without changing the saved base path."""

    def _context_for_job(self, job, *, progress_cb=None, log_cb=None, cancelled_cb=None):
        ctx = super()._context_for_job(
            job,
            progress_cb=progress_cb,
            log_cb=log_cb,
            cancelled_cb=cancelled_cb,
        )
        effective = getattr(job, "_effective_work_operations", None)
        if effective is not None:
            ctx.work_operations = Path(effective)
        return ctx


class WorkflowApp(A35WorkflowApp):
    """a16.4.7: recovery plus job-list output subfolder rules and collision-safe artifacts."""

    def __init__(self) -> None:
        super().__init__()
        if not hasattr(self.jobs, "output_subfolder_rule"):
            self.jobs.output_subfolder_rule = ""
        # Replace the runner with the same core runner contract plus effective Work path.
        self.job_runner = RuleAwareJobRunner(self.registry, self.executor, self.settings)
        self.batch_runner = BatchRunner(self.job_runner)

    @classmethod
    def _recoverable_storage_failure(cls, job) -> bool:
        if getattr(job, "status", None) != JobStatus.FAILED:
            return False

        message = str(getattr(job, "message", "") or "")
        if message.startswith("Lagring utilgjengelig - kan fortsette"):
            return True
        if cls._looks_like_io_failure(message):
            return True

        entries = list(getattr(job, "log_entries", ()) or ())
        recent = "\n".join(str(entry) for entry in entries[-120:])
        return (
            "GJENOPPRETTING: eldre lagringsfeil klassifisert som" in recent
            or "LAGRINGSFEIL: recovery avbrutt; kan forsøkes igjen" in recent
        )

    def _job_position(self, job) -> int:
        for position, candidate in enumerate(self.jobs.jobs(), start=1):
            if candidate.job_id == job.job_id:
                return position
        return 1

    def _apply_effective_work_operations(self, job) -> None:
        rule = str(getattr(self.jobs, "output_subfolder_rule", "") or "")
        effective = effective_work_operations(
            job.work_operations,
            rule,
            job,
            self._job_position(job),
        )
        job._effective_work_operations = effective
        if effective is not None:
            effective.mkdir(parents=True, exist_ok=True)

    def _normalise_job_before_run(self, job) -> None:
        self._apply_effective_work_operations(job)
        super()._normalise_job_before_run(job)

    def _get_output_subfolder_rule(self) -> str:
        return str(getattr(self.jobs, "output_subfolder_rule", "") or "")

    def _set_output_subfolder_rule(self, rule: str) -> tuple[bool, str]:
        rule = str(rule or "").strip()
        try:
            validate_output_subfolder_rule(rule, self.jobs.jobs())
        except OutputSubfolderRuleError as exc:
            return False, str(exc)

        previous = self._get_output_subfolder_rule()
        self.jobs.output_subfolder_rule = rule
        for job in self.jobs.jobs():
            self._apply_effective_work_operations(job)

        if self.job_list_path is not None and not self._save_job_list():
            self.jobs.output_subfolder_rule = previous
            return False, "Kunne ikke lagre undermappe-regelen i jobblisten."

        return True, "Undermappe-regel lagret."

    def _new_job_list(self) -> bool:
        created = super()._new_job_list()
        if created:
            self.jobs.output_subfolder_rule = ""
        return created

    def _load_job_list_file(self, path: Path, *, show_error: bool) -> bool:
        try:
            loaded = load_job_list(path)
        except Exception:
            return super()._load_job_list_file(path, show_error=show_error)

        self.jobs.output_subfolder_rule = loaded.output_subfolder_rule
        ok = super()._load_job_list_file(path, show_error=show_error)
        if ok:
            self.jobs.output_subfolder_rule = loaded.output_subfolder_rule
            for job in self.jobs.jobs():
                self._apply_effective_work_operations(job)
        return ok

    def _open_jobs(self) -> None:
        self._capture_job_operation_params(self.current_job)
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.focus()
            self.jobs_window.refresh()
            return
        self.jobs_window = A20JobsWindow(
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
        )

    def _execute_job(self, job, *, batch_mode: bool) -> bool:
        self._apply_effective_work_operations(job)

        if not self._recoverable_storage_failure(job):
            return super()._execute_job(job, batch_mode=batch_mode)

        cursor = int(job.next_operation_index or 0)
        params_before = dict(job.operation_params or {})

        self._job_log(
            job,
            f"GJENOPPTAR: operasjon {cursor + 1} etter lagringsfeil "
            "(cursor og operasjonsparametre beholdes)",
        )

        job.status = JobStatus.READY
        job.message = f"Gjenopptar fra operasjon {cursor + 1}"
        job.operation_params = params_before

        saved_jobs_window = self.jobs_window
        self.jobs_window = None
        try:
            ok = A28WorkflowApp._execute_job(
                self,
                job,
                batch_mode=batch_mode,
            )
        finally:
            self.jobs_window = saved_jobs_window

        if (
            not ok
            and job.status == JobStatus.FAILED
            and self._looks_like_io_failure(job.message)
        ):
            raw = str(job.message or "")
            prefix = "Lagring utilgjengelig - kan fortsette"
            if not raw.startswith(prefix):
                job.message = f"{prefix}: {raw}"
            self._job_log(
                job,
                "LAGRINGSFEIL: recovery avbrutt; kan forsøkes igjen fra "
                "samme feilede operasjon",
            )

        if saved_jobs_window is not None:
            try:
                if saved_jobs_window.winfo_exists():
                    self.after(0, saved_jobs_window.refresh)
            except Exception:
                pass

        return ok

    def _confirm_rerun(self, jobs) -> bool:
        """Confirm only ordinary reruns; recoverable storage failures continue."""
        previous = [
            job for job in jobs
            if not self._recoverable_storage_failure(job)
        ]
        if not previous:
            return True

        shown = previous[:6]
        sections = [self._rerun_context_for_job(job) for job in shown]
        if len(previous) > len(shown):
            sections.append(f"... og {len(previous) - len(shown)} jobb(er) til")

        message = (
            "Følgende kjøring er planlagt:\n\n"
            + "\n\n".join(sections)
            + "\n\nTidligere resultatmapper slettes ikke. "
              "Den nye kjøringen dokumenteres som en ny hendelse.\n\n"
              "Fortsette?"
        )
        return messagebox.askyesno(APP_NAME, message)


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
