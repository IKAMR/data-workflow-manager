from __future__ import annotations

from . import theme
from .persistent_app_a26_6 import WorkflowApp as A26_6WorkflowApp
from noark5_workflow.external_tools.arkade5_jobs import run_arkade5_plan


class WorkflowApp(A26_6WorkflowApp):
    """v0.1.6-a26.7: live Arkade CLI status while external runs execute."""

    def _a266_run_plan(self, plans, on_progress, on_output):
        summary = run_arkade5_plan(
            self.settings,
            tuple(plans),
            on_progress=on_progress,
            on_output=on_output,
        )
        try:
            self.status_bar.set_status(
                f"Arkade 5: {summary.succeeded} CLI-kjøring(er) fullført, {summary.failed} feil"
            )
        except Exception:
            pass
        return summary


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
