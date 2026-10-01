from __future__ import annotations

from noark5_workflow.job_batch_actions import discover_arkade5_results_for_jobs
from . import theme
from .arkade5_batch_discovery_dialog import Arkade5BatchDiscoveryDialog
from .persistent_app_a25_1 import WorkflowApp as A25_1WorkflowApp


class WorkflowApp(A25_1WorkflowApp):
    """v0.1.6-a25.2: visible Arkade search progress and per-job correlation."""

    def _a252_progress(self, text: str) -> None:
        try:
            self.status_bar.set_status(text)
        except Exception:
            pass
        # Paint the status before a potentially slow filesystem scan continues.
        for widget in (self.jobs_window, self):
            if widget is None:
                continue
            try:
                widget.update_idletasks()
            except Exception:
                pass

    # A25.1's Jobs window callback is intentionally kept stable; overriding the
    # callback implementation here lets the active A32 window use a25.2 logic.
    def _a251_discover_arkade5_results(self, jobs) -> None:
        selected = tuple(jobs)
        if not selected:
            return

        self._a252_progress(
            f"Søker etter Arkade 5-resultater for {len(selected)} jobb(er) …"
        )
        result = discover_arkade5_results_for_jobs(
            selected,
            configured_roots=self._a251_configured_roots(self.settings),
            on_progress=self._a252_progress,
        )

        self._a252_progress(
            f"Arkade 5: {result.reports_found} rapportkoblinger i "
            f"{result.jobs_with_results} av {result.selected_jobs} jobber"
        )

        dialog = Arkade5BatchDiscoveryDialog(self.jobs_window or self, result)
        dialog.focus()
        dialog.lift()


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
