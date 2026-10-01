from __future__ import annotations

from typing import Callable

from noark5_workflow.core.job import Job
from .job_batch_action_dialog import JobBatchActionDialog
from .jobs_window_a32 import A32JobsWindow


class A33JobsWindow(A32JobsWindow):
    """a26.6: add Arkade 5 CLI execution to reusable selected-job actions."""

    def __init__(
        self,
        *args,
        on_run_arkade5: Callable[[tuple[Job, ...]], None] | None = None,
        **kwargs,
    ) -> None:
        self.on_run_arkade5 = on_run_arkade5 or (lambda _jobs: None)
        super().__init__(*args, **kwargs)

    def _open_job_actions(self) -> None:
        if self._batch_running:
            return
        existing = self._job_actions_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.focus()
                    existing.lift()
                    return
            except Exception:
                self._job_actions_dialog = None

        dialog = JobBatchActionDialog(
            self,
            self.batch.jobs(),
            on_fill_storage_suggestions=self._run_fill_storage_suggestions,
            on_discover_arkade5_results=self._run_discover_arkade5_results,
            on_run_arkade5=self._run_arkade5,
        )
        self._job_actions_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._job_actions_closed(event, d),
            add="+",
        )

    def _run_arkade5(self, jobs: tuple[Job, ...]) -> None:
        self.on_run_arkade5(jobs)
