from __future__ import annotations

from tkinter import messagebox

from noark5_workflow.job_batch_actions import (
    discover_arkade5_results_for_jobs,
    fill_missing_storage_suggestions,
    preview_missing_storage_suggestions,
)
from version import APP_NAME
from . import theme
from .arkade5_batch_discovery_dialog import Arkade5BatchDiscoveryDialog
from .persistent_app_a25_2 import WorkflowApp as A25_2WorkflowApp
from .storage_suggestion_preview_dialog import StorageSuggestionPreviewDialog


class WorkflowApp(A25_2WorkflowApp):
    """v0.1.6-a25.3: explicit review before batch map fill and Arkade use."""

    def _a246_fill_storage_suggestions(self, jobs) -> None:
        """A25.3 turns the old immediate batch fill into a review-first action."""
        selected = tuple(jobs)
        if not selected:
            return
        layout_id = str(
            self.settings.get("storage_layout_profile", "ikamr_standard") or "none"
        )
        preview = preview_missing_storage_suggestions(
            selected,
            layout_id=layout_id,
        )
        rows = tuple(zip(selected, preview))
        dialog = StorageSuggestionPreviewDialog(
            self.jobs_window or self,
            rows,
            on_apply=lambda chosen: self._a253_apply_storage_suggestions(
                chosen, layout_id=layout_id
            ),
        )
        dialog.focus()
        dialog.lift()

    def _a253_apply_storage_suggestions(self, jobs, *, layout_id: str) -> None:
        selected = tuple(jobs)
        if not selected:
            return
        result = fill_missing_storage_suggestions(selected, layout_id=layout_id)

        if self.job_list_path is not None:
            self._write_job_list(self.job_list_path)
        if self.jobs_window is not None:
            try:
                self.jobs_window.refresh()
                self.jobs_window._refresh_output_rule_preview()
            except Exception:
                pass
        if self.current_job in selected:
            try:
                self._refresh_active_job_label()
            except Exception:
                pass
        try:
            self.status_bar.set_status(
                f"Mappeforslag: {result.filled_fields} felt i "
                f"{result.changed_jobs} av {result.selected_jobs} jobber"
            )
        except Exception:
            pass

        messagebox.showinfo(
            APP_NAME,
            "Mappeforslag er behandlet.\n\n"
            f"Valgte jobber: {result.selected_jobs}\n"
            f"Jobber endret: {result.changed_jobs}\n"
            f"Tomme felt fylt: {result.filled_fields}\n"
            f"Uten beregnbare forslag: {result.jobs_without_suggestions}\n\n"
            "Eksisterende mappevalg ble ikke overskrevet.",
            parent=self.jobs_window,
        )

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
        dialog = Arkade5BatchDiscoveryDialog(
            self.jobs_window or self,
            result,
            on_accept=self._a253_accept_arkade5_results,
        )
        dialog.focus()
        dialog.lift()

    def _a253_accept_arkade5_results(self, selected) -> None:
        """Keep the explicit user selection for the next Arkade batch step.

        A25.3 still does not import/copy reports. The selection is intentionally
        transient until a later step defines the import/run action contract.
        """
        self._a253_selected_arkade5_results = tuple(selected)
        count = len(self._a253_selected_arkade5_results)
        job_count = len({job_id for job_id, _candidate in self._a253_selected_arkade5_results})
        try:
            self.status_bar.set_status(
                f"Arkade 5: {count} rapport(er) valgt for videre behandling i {job_count} jobb(er)"
            )
        except Exception:
            pass
        messagebox.showinfo(
            APP_NAME,
            f"{count} Arkade 5-rapport(er) er valgt for videre behandling.\n\n"
            "Ingen resultater er importert eller kopiert i a25.3.",
            parent=self.jobs_window,
        )


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
