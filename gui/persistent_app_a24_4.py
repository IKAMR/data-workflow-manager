from __future__ import annotations

from pathlib import Path

from noark5_workflow.extraction_discovery import ExtractionCandidate, ExtractionDiscoveryResult
from . import theme
from .persistent_app_a24_3 import WorkflowApp as A24_3WorkflowApp


class WorkflowApp(A24_3WorkflowApp):
    """v0.1.6-a24.4: keep source root distinct from the discovered extraction."""

    def _a243_add_selected_candidates(
        self,
        result: ExtractionDiscoveryResult,
        selected: tuple[ExtractionCandidate, ...],
    ) -> None:
        if not selected:
            return

        definition = result.definition
        jobs_before = self.jobs.jobs()
        reusable = (
            jobs_before[0]
            if len(jobs_before) == 1 and jobs_before[0].is_unused_draft()
            else None
        )

        created = []
        for index, candidate in enumerate(selected):
            extraction = Path(candidate.path)
            source_root = Path(candidate.source_root_hint or extraction.parent)
            if index == 0 and reusable is not None:
                job = reusable
            else:
                # _create_job is still used for the common job identity/setup path,
                # but the source contract is assigned explicitly below.
                job = self._create_job(extraction)

            job.source_root = source_root
            job.source_extraction = extraction
            job.profile_id = candidate.profile_id or definition.profile_id
            job.name = candidate.suggested_name or extraction.name or job.job_id
            created.append(job)

        if reusable is not None and self.current_job is reusable:
            self._refresh_active_job_label()

        if self.job_list_path is not None:
            self._write_job_list(self.job_list_path)

        if self.jobs_window is not None:
            try:
                self.jobs_window.refresh()
            except Exception:
                pass

        try:
            self.status_bar.set_status(
                f"La til {len(created)} {definition.label}-uttrekk"
            )
        except Exception:
            pass

        from tkinter import messagebox
        from version import APP_NAME
        messagebox.showinfo(
            APP_NAME,
            f"{len(created)} {definition.label}-uttrekk ble lagt til som jobber.",
            parent=self.jobs_window,
        )


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
