from __future__ import annotations

from noark5_workflow.core.joblist_context import JobListContext

from . import theme
from .persistent_app_a26_9 import WorkflowApp as A26_9WorkflowApp


class WorkflowApp(A26_9WorkflowApp):
    """v0.1.6-a27.1: explicit job-list + active-job working context.

    This layer intentionally does not add a second mutable job-list state.
    It projects the existing authoritative runtime state into one shared
    context object that later main-window, batch, CLI and server work can use.
    """

    def _a271_joblist_context(self) -> JobListContext:
        return JobListContext.from_runtime_state(
            self.jobs.jobs(),
            self.current_job,
            self.job_list_path,
        )

    @property
    def joblist_context(self) -> JobListContext:
        """Current DWM working context, always derived from live runtime state."""
        return self._a271_joblist_context()


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
