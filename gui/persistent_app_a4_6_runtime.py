"""Keep Resultatvisninger and technical raw results distinct.

A depot report is required for the existing Resultatvisninger model.
Never silently open the editable depot assessment window instead.
"""
from __future__ import annotations

from tkinter import messagebox
import customtkinter as ctk

from .persistent_app_v017_a2 import WorkflowApp as V017A2WorkflowApp


class WorkflowApp(V017A2WorkflowApp):
    def __init__(self):
        super().__init__()
        splitter = getattr(self, "bottom_splitter", None)
        if splitter is not None:
            splitter.configure(border_width=0)
        self.after_idle(self._v017_arrange_log_actions)

    def _open_depot_assessment(self) -> None:
        """Open Resultatvisninger only when its source report is usable.

        The v0.1.7-a1 fallback called the old Depotvurdering window when
        report discovery failed. That made the Resultatvisninger button appear
        wired to a different action on jobs without a depot report.
        """
        job = getattr(self, "current_job", None)
        if job is None:
            messagebox.showinfo(
                "Resultatvisninger – Noark 5",
                "Ingen aktiv jobb er valgt.", parent=self,
            )
            return
        try:
            report_path, _work_operations, _unavailable = self._depot_report_for_job(job)
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showwarning(
                "Resultatvisninger – Noark 5",
                f"Kan ikke finne depotvalideringsrapport for aktiv jobb: {exc}",
                parent=self,
            )
            return
        if report_path is None:
            messagebox.showinfo(
                "Resultatvisninger – Noark 5",
                "Ingen depotvalideringsrapport er funnet for aktiv jobb.\n\n"
                "Resultatvisninger krever en generert depotvalideringsrapport. "
                "Kjør operasjonen 'Noark 5 depotvalideringsrapport' for denne "
                "jobben, eller velg en eksisterende rapport i rapportvisningen.\n\n"
                "Eksisterende XPath- og Arkade 5-resultater blir ikke slettet.",
                parent=self,
            )
            return
        # With an existing report, retain the established a12/a13 result centre.
        return super()._open_depot_assessment()

    def _v017_arrange_log_actions(self) -> None:
        """Rename the existing entry action, preserving its report handler."""
        header = getattr(getattr(self, "log_panel", None), "header", None)
        if header is None:
            return
        found = {}
        for child in header.winfo_children():
            if isinstance(child, ctk.CTkButton):
                label = str(child.cget("text"))
                if label in {"Resultater", "Råresultater", "Depotvurdering", "Resultatvisninger", "Tøm"}:
                    found[label] = child
        raw = found.get("Råresultater") or found.get("Resultater")
        depot = found.get("Resultatvisninger") or found.get("Depotvurdering")
        clear = found.get("Tøm")
        if raw is not None:
            raw.configure(text="Råresultater", width=92)
        if depot is not None:
            depot.configure(text="Resultatvisninger", width=118)
        for widget in (raw, depot, clear):
            if widget is not None and widget.grid_info():
                widget.grid_remove()
        for column, widget in ((1, depot), (2, raw), (3, clear)):
            if widget is not None:
                widget.grid(row=0, column=column, padx=(4, 0), pady=0, sticky="e")
        header.grid_columnconfigure(0, weight=1)
        for column in range(1, 4):
            header.grid_columnconfigure(column, weight=0)
