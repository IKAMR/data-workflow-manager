from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from noark5_workflow.external_evidence.arkade5 import (
    infer_work_operations_from_depot_report,
    list_arkade5_imports,
    load_arkade5_import,
)
from noark5_workflow.external_evidence.arkade5_analysis import build_arkade5_analysis
from version import APP_NAME
from . import theme
from .arkade5_analysis_dialog_a14 import Arkade5AnalysisDialog
from .depot_result_views_a13 import DepotResultViewsDialogA13


class Arkade5AnalysisSelectionDialog(ctk.CTkToplevel):
    def __init__(self, master, *, work_operations, imports, open_import) -> None:
        super().__init__(master)
        self.title("Velg Arkade 5-rapport for analyse")
        self.geometry("1180x620")
        self.minsize(900, 480)
        self.transient(master)
        self.work_operations = work_operations
        self._open_import = open_import

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text=(
                f"Fant {len(imports)} importerte Arkade 5-rapporter. "
                "Velg rapporten som skal analyseres."
            ),
            anchor="w",
            justify="left",
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))

        frame = ctk.CTkScrollableFrame(self)
        frame.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 10))
        frame.grid_columnconfigure(0, weight=1)

        for row_no, item in enumerate(imports):
            summary = item.get("source_summary") or {}
            source = item.get("source") or {}
            ctk.CTkLabel(
                frame,
                text=(
                    f"Testdato: {summary.get('date_of_testing') or '–'}  |  "
                    f"Tester: {summary.get('number_of_tests_run') or '–'}  |  "
                    f"Errors: {summary.get('number_of_errors') or 0}  |  "
                    f"Warnings: {summary.get('number_of_warnings') or 0}\n"
                    f"Import-ID: {item.get('import_id') or '–'}\n"
                    f"Kilde: {source.get('original_name') or '–'}"
                ),
                anchor="w",
                justify="left",
                wraplength=900,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=row_no, column=0, sticky="ew", padx=6, pady=7)

            ctk.CTkButton(
                frame,
                text="Analyser",
                width=110,
                command=lambda selected=item: self._choose(selected),
            ).grid(row=row_no, column=1, padx=6, pady=7)

        ctk.CTkButton(
            self,
            text="Lukk",
            width=90,
            command=self.destroy,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=2, column=0, sticky="e", padx=18, pady=(0, 18))

        self.after_idle(self.lift)
        self.after_idle(self.focus_force)

    def _choose(self, selected) -> None:
        self.destroy()
        self._open_import(self.work_operations, selected)


class DepotResultViewsDialogA14(DepotResultViewsDialogA13):
    def _build_external_evidence_tab(self, tab) -> None:
        super()._build_external_evidence_tab(tab)

        analysis = ctk.CTkFrame(tab, fg_color="transparent")
        analysis.grid(row=5, column=0, sticky="ew", padx=8, pady=(0, 8))
        analysis.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            analysis,
            text=(
                "Analyser Arkade 5-rapporten i en menneskevennlig visning med "
                "prioriterte feil, advarsler, vurderingspunkter, DWM-dekning og "
                "sporbare Arkade-funn."
            ),
            anchor="w",
            justify="left",
            wraplength=720,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            analysis,
            text="Analyser Arkade 5...",
            width=150,
            state="normal" if self.report_path else "disabled",
            command=self._open_arkade5_analysis,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)

    def _open_arkade5_analysis(self) -> None:
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

        if len(imports) == 1:
            self._open_arkade5_analysis_for_import(work, imports[0])
            return

        Arkade5AnalysisSelectionDialog(
            self,
            work_operations=work,
            imports=imports,
            open_import=self._open_arkade5_analysis_for_import,
        )

    def _open_arkade5_analysis_for_import(self, work, selected) -> None:
        try:
            loaded = load_arkade5_import(work, str(selected.get("import_id")))
            analysis = build_arkade5_analysis(
                loaded["normalized"],
                loaded.get("reconciliation"),
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        summary = selected.get("source_summary") or {}
        label = (
            f"Arkade 5  |  Testdato: {summary.get('date_of_testing') or '–'}  |  "
            f"Import-ID: {selected.get('import_id') or '–'}"
        )
        Arkade5AnalysisDialog(self, analysis=analysis, source_label=label)
