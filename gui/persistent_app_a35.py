from __future__ import annotations

from . import theme
from .persistent_app_a34 import WorkflowApp as A34WorkflowApp


class WorkflowApp(A34WorkflowApp):
    """a16.4.6.5: let recoverable storage failures enter recovery directly.

    A recoverable FAILED job is not an ordinary terminal rerun. The established
    _run_workflow() path asks _confirm_rerun() for terminal jobs before it calls
    _execute_job(), which can block the recovery handoff. Exclude recoverable
    storage failures from that rerun confirmation while preserving the normal
    confirmation for every other previously-run job.
    """

    def _confirm_rerun(self, jobs) -> bool:
        ordinary_reruns = [
            job for job in jobs
            if not self._recoverable_storage_failure(job)
        ]
        if not ordinary_reruns:
            return True
        return super()._confirm_rerun(ordinary_reruns)


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
