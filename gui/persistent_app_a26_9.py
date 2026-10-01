from __future__ import annotations

from dataclasses import replace

from . import theme
from .persistent_app_a26_8 import WorkflowApp as A26_8WorkflowApp
from noark5_workflow.external_tools.arkade5_auto_import import import_arkade5_run_outputs


class WorkflowApp(A26_8WorkflowApp):
    """v0.1.6-a26: automatically import evidence produced by DWM Arkade runs."""

    def _a266_run_plan(self, plans, on_progress, on_output):
        plans = tuple(plans)
        summary = super()._a266_run_plan(plans, on_progress, on_output)

        def import_progress(text: str) -> None:
            if plans and on_output is not None:
                try:
                    on_output(0, 0, plans[-1], "stdout", f"[DWM] {text}\n")
                except Exception:
                    pass

        auto_import = import_arkade5_run_outputs(
            summary,
            on_progress=import_progress,
        )
        summary = replace(summary, auto_import=auto_import)
        try:
            self.status_bar.set_status(
                "Arkade 5: "
                f"{summary.succeeded} CLI fullført, "
                f"{auto_import.imported} rapport(er) importert, "
                f"{auto_import.pronom_attached} PRONOM koblet"
            )
        except Exception:
            pass
        return summary


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
