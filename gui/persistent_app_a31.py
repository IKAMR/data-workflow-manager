from __future__ import annotations

from pathlib import Path

from noark5_workflow.core.job import JobStatus
from . import theme
from .persistent_app_a28 import WorkflowApp as A28WorkflowApp
from .persistent_app_a30 import WorkflowApp as A30WorkflowApp


_RECOVERABLE_STORAGE_PREFIX = "Lagring utilgjengelig - kan fortsette"


class WorkflowApp(A30WorkflowApp):
    """a16.4.3: reliable recovery handoff + tolerant source preflight.

    Two fixes:
    1. A recoverable FAILED job is handed directly to the established WAITING
       resume path, bypassing the a16.3 wrapper that could stall before START.
    2. Preflight accepts an available source_root when a stored
       source_extraction path is stale/more specific and temporarily missing.
    """

    # ------------------------------------------------------------------
    # Source/work availability
    # ------------------------------------------------------------------

    @staticmethod
    def _path_is_available(path: Path | None) -> bool:
        if path is None:
            return False
        try:
            return Path(path).exists()
        except OSError:
            return False

    def _storage_problems(self, job) -> list[str]:
        problems: list[str] = []

        extraction = job.source_extraction
        root = job.source_root

        # A job may carry both package root and extraction root. For preflight,
        # at least one authoritative Source location being available is enough;
        # execution/configuration will resolve the exact extraction as usual.
        if not (
            self._path_is_available(extraction)
            or self._path_is_available(root)
        ):
            if extraction is not None and root is not None:
                problems.append(
                    "Source er ikke tilgjengelig: "
                    f"{extraction} (heller ikke Source root: {root})"
                )
            elif extraction is not None:
                problems.append(f"Source er ikke tilgjengelig: {extraction}")
            elif root is not None:
                problems.append(f"Source er ikke tilgjengelig: {root}")
            else:
                problems.append("Source mangler")

        work_anchor = job.work_root
        if work_anchor is not None:
            if not self._path_is_available(Path(work_anchor)):
                problems.append(f"Work er ikke tilgjengelig: {work_anchor}")
        elif job.work_operations is not None:
            existing = self._nearest_existing_parent(Path(job.work_operations))
            if existing is None:
                problems.append(
                    "Work operations har ingen tilgjengelig overmappe: "
                    f"{job.work_operations}"
                )

        return problems

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    def _execute_job(self, job, *, batch_mode: bool) -> bool:
        if not self._recoverable_storage_failure(job):
            return super()._execute_job(job, batch_mode=batch_mode)

        # Preserve absolutely everything needed for retry before changing state.
        cursor = int(job.next_operation_index or 0)
        params_before = dict(job.operation_params or {})
        old_message = str(job.message or "")

        self._job_log(
            job,
            f"GJENOPPTAR: operasjon {cursor + 1} etter lagringsfeil "
            "(cursor og operasjonsparametre beholdes)",
        )

        # The long-established executor resumes only from WAITING. Put the job
        # into that state *before* entering the normal execution chain.
        job.status = JobStatus.WAITING
        job.message = f"Gjenopptar fra operasjon {cursor + 1}"

        # Defensive contract: recovery must not mutate operation parameters.
        job.operation_params = params_before

        if self.job_list_path is not None:
            self._write_job_list(self.job_list_path)

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.after(0, self.jobs_window.refresh)
            except Exception:
                pass

        # IMPORTANT: bypass A29's recovery wrapper. Call the pre-a16.3
        # execution chain directly. It already has proven WAITING/cursor resume
        # semantics and will emit "Workflow fortsetter..." then START.
        ok = A28WorkflowApp._execute_job(
            self,
            job,
            batch_mode=batch_mode,
        )

        # New I/O failure on the retry must again become recoverable.
        if (
            not ok
            and job.status == JobStatus.FAILED
            and self._looks_like_io_failure(job.message)
        ):
            raw = str(job.message or old_message)
            if not raw.startswith(_RECOVERABLE_STORAGE_PREFIX):
                job.message = f"{_RECOVERABLE_STORAGE_PREFIX}: {raw}"
            self._job_log(
                job,
                "LAGRINGSFEIL: recovery avbrutt; kan forsøkes igjen fra "
                "samme feilede operasjon",
            )
            if self.job_list_path is not None:
                self._write_job_list(self.job_list_path)

        return ok


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
