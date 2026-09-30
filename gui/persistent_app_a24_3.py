from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from noark5_workflow.extraction_discovery import ExtractionCandidate, ExtractionDiscoveryResult
from version import APP_NAME
from . import theme
from .extraction_candidate_selection_dialog import ExtractionCandidateSelectionDialog
from .persistent_app_a24_2 import WorkflowApp as A24_2WorkflowApp


class WorkflowApp(A24_2WorkflowApp):
    """v0.1.6-a24.3: selectable discovery results and complete job initialization."""

    def _a242_apply_discovery(self, result: ExtractionDiscoveryResult) -> None:
        definition = result.definition
        if not result.candidates:
            extra = ""
            if result.scanned_directories:
                extra += f"\nMapper kontrollert: {result.scanned_directories}"
            if result.errors:
                extra += f"\nMapper som ikke kunne leses: {len(result.errors)}"
            messagebox.showinfo(
                APP_NAME,
                f"Ingen {definition.label}-uttrekk ble funnet.\n\n"
                f"Søkegrunnlag: {result.source_label}{extra}",
                parent=self.jobs_window,
            )
            return

        existing = {
            self._a242_path_key(job.active_extraction_root)
            for job in self.jobs.jobs()
            if job.active_extraction_root is not None
        }
        new_candidates = tuple(
            item
            for item in result.candidates
            if self._a242_path_key(item.path) not in existing
        )
        duplicate_count = len(result.candidates) - len(new_candidates)

        if not new_candidates:
            messagebox.showinfo(
                APP_NAME,
                f"Fant {len(result.candidates)} {definition.label}-uttrekk, "
                "men alle finnes allerede i jobblista.",
                parent=self.jobs_window,
            )
            return

        source_kind = "Søk i mapper" if result.source_kind == "folders" else "Søk fra liste"
        source_summary = source_kind
        if duplicate_count:
            source_summary += f" | {duplicate_count} finnes allerede i jobblista"
        if result.scanned_directories:
            source_summary += f" | {result.scanned_directories} mapper kontrollert"

        ExtractionCandidateSelectionDialog(
            self.jobs_window or self,
            new_candidates,
            extraction_label=definition.label,
            source_label=source_summary,
            on_confirm=lambda selected: self._a243_add_selected_candidates(result, selected),
        )

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
            path = Path(candidate.path)
            if index == 0 and reusable is not None:
                job = reusable
            else:
                job = self._create_job(path)

            # The generic discovery path must initialize every discovered job in
            # the same way. In a24.2 only source_extraction was assigned for jobs
            # after the first, leaving their visible/source state incomplete.
            job.source_root = path
            job.source_extraction = path
            job.profile_id = candidate.profile_id or definition.profile_id
            job.name = candidate.suggested_name or path.name or job.job_id
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

        messagebox.showinfo(
            APP_NAME,
            f"{len(created)} {definition.label}-uttrekk ble lagt til som jobber.",
            parent=self.jobs_window,
        )


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
