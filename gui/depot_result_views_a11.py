from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from noark5_workflow.external_evidence.arkade5 import (
    Arkade5ImportError,
    import_arkade5_report,
    infer_work_operations_from_depot_report,
)
from noark5_workflow.external_evidence.arkade5_discovery import (
    Arkade5Candidate,
    discover_arkade5_reports,
)
from version import APP_NAME
from . import theme
from .depot_result_views import DepotResultViewsDialog


class Arkade5DiscoveryDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        *,
        candidates: list[Arkade5Candidate],
        import_candidate,
    ) -> None:
        super().__init__(master)
        self.title("Finn Arkade 5-rapporter")
        self.geometry("1100x650")
        self.minsize(850, 520)
        self.transient(master)
        self._import_candidate = import_candidate

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text=(
                f"Fant {len(candidates)} gyldig(e) Arkade 5 Noark 5-rapport(er) "
                "under jobbroten. Velg hvilken rapport som skal importeres som ekstern evidens."
            ),
            anchor="w",
            justify="left",
            wraplength=1040,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))

        frame = ctk.CTkScrollableFrame(self)
        frame.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 10))
        frame.grid_columnconfigure(0, weight=1)

        for row, candidate in enumerate(candidates):
            text = (
                f"{candidate.path}\n"
                f"Testdato: {candidate.test_date or '–'} | Tester: {candidate.tests_run} | "
                f"Errors: {candidate.errors} | Warnings: {candidate.warnings}"
            )
            ctk.CTkLabel(
                frame,
                text=text,
                anchor="w",
                justify="left",
                wraplength=850,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=row, column=0, sticky="ew", padx=6, pady=7)
            ctk.CTkButton(
                frame,
                text="Importer",
                width=90,
                command=lambda c=candidate: self._choose(c),
            ).grid(row=row, column=1, padx=6, pady=7)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            bottom,
            text="Lukk",
            width=90,
            command=self.destroy,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)

        self.after_idle(self.lift)
        self.after_idle(self.focus_force)

    def _choose(self, candidate: Arkade5Candidate) -> None:
        if self._import_candidate(candidate):
            self.destroy()


class DepotResultViewsDialogA11(DepotResultViewsDialog):
    """Adds discovery/automatic import of existing Arkade 5 reports."""

    def _build_external_evidence_tab(self, tab) -> None:
        super()._build_external_evidence_tab(tab)

        # Parent implementation creates a button row at row=1. Add the discovery
        # action as a separate row to avoid depending on its internal widget refs.
        discovery = ctk.CTkFrame(tab, fg_color="transparent")
        discovery.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        discovery.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            discovery,
            text=(
                "Søk gjennom jobbroten etter eksisterende Arkade 5 JSON-rapporter. "
                "Kun filer som faktisk validerer som Arkade 5 Noark 5-testrapporter vises."
            ),
            anchor="w",
            justify="left",
            wraplength=720,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            discovery,
            text="Finn Arkade 5...",
            width=135,
            state="normal" if self.report_path else "disabled",
            command=self._discover_arkade5_evidence,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)

    def _discover_arkade5_evidence(self) -> None:
        if self.report_path is None:
            return

        try:
            candidates = discover_arkade5_reports(self.report_path)
        except (OSError, ValueError) as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        if not candidates:
            messagebox.showinfo(
                APP_NAME,
                "Fant ingen gyldige Arkade 5 Noark 5-rapporter under jobbroten.",
                parent=self,
            )
            return

        if len(candidates) == 1:
            candidate = candidates[0]
            if messagebox.askyesno(
                APP_NAME,
                "Fant én gyldig Arkade 5-rapport:\n\n"
                f"{candidate.path}\n\n"
                "Importere den som ekstern evidens?",
                parent=self,
            ):
                self._import_discovered_candidate(candidate)
            return

        Arkade5DiscoveryDialog(
            self,
            candidates=candidates,
            import_candidate=self._import_discovered_candidate,
        )

    def _import_discovered_candidate(self, candidate: Arkade5Candidate) -> bool:
        if self.report_path is None:
            return False
        try:
            work_operations = infer_work_operations_from_depot_report(self.report_path)
            manifest = import_arkade5_report(
                candidate.path,
                work_operations=work_operations,
                depot_report_path=self.report_path,
                imported_by=self.user_identity,
            )
        except (Arkade5ImportError, OSError, ValueError) as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return False

        self._external_evidence_import = manifest
        self._refresh_external_evidence()
        rec = manifest.get("reconciliation_summary") or {}
        messagebox.showinfo(
            APP_NAME,
            "Arkade 5-rapport importert som ekstern evidens.\n\n"
            f"Match: {rec.get('match', 0)}\n"
            f"Mismatch: {rec.get('mismatch', 0)}\n"
            f"Ikke tilgjengelig: {rec.get('not_available', 0)}",
            parent=self,
        )
        return True
