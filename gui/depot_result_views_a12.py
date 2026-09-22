from __future__ import annotations

import json
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from noark5_workflow.external_evidence.arkade5 import (
    infer_work_operations_from_depot_report,
    list_arkade5_imports,
    load_arkade5_import,
)
from noark5_workflow.external_evidence.arkade5_coverage import build_arkade5_coverage
from version import APP_NAME
from . import theme
from .depot_result_views_a11 import DepotResultViewsDialogA11


_CLASS_LABEL = {
    "equivalent": "Direkte sammenlignbar",
    "candidate": "Kandidat – må kvalitetssikres",
    "known_non_equivalent": "Ikke direkte sammenlignbar",
    "unmapped": "Ikke kartlagt",
}


class Arkade5CoverageDialog(ctk.CTkToplevel):
    def __init__(self, master, *, coverage: dict, source_label: str) -> None:
        super().__init__(master)
        self.title("Arkade 5 – DWM testdekning")
        self.geometry("1450x800")
        self.minsize(1050, 620)
        self.transient(master)
        self.coverage = coverage

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            self,
            text="ARKADE 5 – DWM TESTDEKNING",
            anchor="w",
            font=theme.font(theme.TITLE_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 4))

        s = coverage["summary"]
        ctk.CTkLabel(
            self,
            text=(
                f"{source_label}\n"
                f"Tester i Arkade-rapport: {coverage['arkade_tests_present']}  |  "
                f"Direkte sammenlignbare: {s['equivalent']}  |  "
                f"Kandidater: {s['candidate']}  |  "
                f"Ikke direkte sammenlignbare: {s['known_non_equivalent']}  |  "
                f"Ikke kartlagt: {s['unmapped']}"
            ),
            anchor="w",
            justify="left",
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 6))

        ctk.CTkLabel(
            self,
            text=(
                "Kandidat betyr at Arkade og DWM peker på samme N5-testpunkt. "
                "Det er ikke det samme som dokumentert ekvivalens. Bare "
                "'Direkte sammenlignbar' inngår i automatisk reconciliation."
            ),
            anchor="w",
            justify="left",
            wraplength=1380,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))

        frame = ctk.CTkScrollableFrame(self)
        frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 10))
        for col, weight in enumerate((0, 2, 0, 2, 3)):
            frame.grid_columnconfigure(col, weight=weight)

        headers = ("Arkade", "Test", "Arkade-status", "Kartlegging", "DWM / begrunnelse")
        for col, label in enumerate(headers):
            ctk.CTkLabel(
                frame, text=label, anchor="w", font=theme.font(theme.SMALL_SIZE)
            ).grid(row=0, column=col, sticky="ew", padx=6, pady=(4, 8))

        for row_no, item in enumerate(coverage["items"], start=1):
            dwm = ", ".join(
                f"{x.get('dwm_test_id')} ({x.get('legacy_job_id')})"
                for x in item.get("dwm_candidates") or []
            )
            detail = dwm or item.get("reason") or "–"
            values = (
                item.get("arkade_test_id"),
                item.get("arkade_test_name"),
                item.get("arkade_status"),
                _CLASS_LABEL.get(item.get("classification"), item.get("classification")),
                detail,
            )
            for col, value in enumerate(values):
                ctk.CTkLabel(
                    frame,
                    text=str(value or "–"),
                    anchor="w",
                    justify="left",
                    wraplength=(480 if col in (1, 4) else 230),
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=row_no, column=col, sticky="new", padx=6, pady=5)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            bottom, text="Lukk", width=90, command=self.destroy,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)

        self.after_idle(self.lift)
        self.after_idle(self.focus_force)


class DepotResultViewsDialogA12(DepotResultViewsDialogA11):
    def _build_external_evidence_tab(self, tab) -> None:
        super()._build_external_evidence_tab(tab)

        coverage = ctk.CTkFrame(tab, fg_color="transparent")
        coverage.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
        coverage.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            coverage,
            text=(
                "Kartlegg alle testene i importert Arkade 5-rapport mot DWM: "
                "dokumentert ekvivalens, kandidat, kjent ikke-ekvivalent eller ikke kartlagt."
            ),
            anchor="w",
            justify="left",
            wraplength=720,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            coverage,
            text="Testdekning...",
            width=125,
            state="normal" if self.report_path else "disabled",
            command=self._open_arkade5_coverage,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)

    def _open_arkade5_coverage(self) -> None:
        if self.report_path is None:
            return
        try:
            work = infer_work_operations_from_depot_report(self.report_path)
            imports = list_arkade5_imports(work)
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        if not imports:
            messagebox.showinfo(
                APP_NAME,
                "Importer eller finn en Arkade 5-rapport først.",
                parent=self,
            )
            return

        # The evidence list is newest import first. Coverage concerns test
        # definitions, so one normalized report is sufficient per source version.
        selected = imports[0]
        try:
            loaded = load_arkade5_import(work, str(selected.get("import_id")))
            coverage = build_arkade5_coverage(loaded["normalized"])
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        summary = selected.get("source_summary") or {}
        label = (
            f"Arkade 5 {selected.get('import_id', '')} | "
            f"Testdato: {summary.get('date_of_testing') or '–'}"
        )
        Arkade5CoverageDialog(self, coverage=coverage, source_label=label)
