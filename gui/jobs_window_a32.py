from __future__ import annotations

from typing import Callable

from noark5_workflow.core.job import Job
from .job_batch_action_dialog import JobBatchActionDialog
from .jobs_window_a31 import A31JobsWindow


class A32JobsWindow(A31JobsWindow):
    """a25.1: Arkade 5 discovery as a reusable action on selected jobs."""

    def __init__(
        self,
        *args,
        on_discover_arkade5_results: Callable[[tuple[Job, ...]], None] | None = None,
        **kwargs,
    ) -> None:
        self.on_discover_arkade5_results = (
            on_discover_arkade5_results or (lambda _jobs: None)
        )
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
        )
        self._job_actions_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._job_actions_closed(event, d),
            add="+",
        )

    def _run_discover_arkade5_results(self, jobs: tuple[Job, ...]) -> None:
        self.on_discover_arkade5_results(jobs)
