from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from noark5_workflow.external_evidence.arkade5 import (
    infer_work_operations_from_depot_report,
    list_arkade5_imports,
    load_arkade5_import,
)
from noark5_workflow.external_evidence.result_bank import (
    build_external_result_bank,
    write_external_result_bank,
)
from version import APP_NAME
from . import theme
from .depot_result_views_a12 import (
    Arkade5CoverageDialog,
    DepotResultViewsDialogA12,
)
from noark5_workflow.external_evidence.arkade5_coverage import build_arkade5_coverage


_RELATION_LABELS = {
    "corroborates_internal": "Bekrefter intern verdi",
    "conflicts_with_internal": "Konflikt med intern verdi",
    "comparison_not_available": "Sammenligning ikke tilgjengelig",
    "external_only_or_unmapped": "Ekstern / ikke kartlagt",
}

_COVERAGE_LABELS = {
    "equivalent": "Direkte sammenlignbar",
    "candidate": "Kandidat",
    "known_non_equivalent": "Ikke direkte sammenlignbar",
    "unmapped": "Ikke kartlagt",
}


def _display(value) -> str:
    return "–" if value in (None, "") else str(value)


class Arkade5CoverageSelectionDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        *,
        work_operations,
        imports: list[dict],
        open_import,
    ) -> None:
        super().__init__(master)
        self.title("Velg Arkade 5-rapport")
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
                "Velg hvilken rapport/kjøring som skal vises i Testdekning."
            ),
            anchor="w",
            justify="left",
            wraplength=1120,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=18,
            pady=(18, 10),
        )

        frame = ctk.CTkScrollableFrame(self)
        frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=18,
            pady=(0, 10),
        )
        frame.grid_columnconfigure(0, weight=1)

        for row_no, item in enumerate(imports):
            summary = item.get("source_summary") or {}
            text = (
                f"Testdato: {summary.get('date_of_testing') or '–'}  |  "
                f"Tester: {summary.get('number_of_tests_run') or '–'}  |  "
                f"Errors: {summary.get('number_of_errors') or 0}  |  "
                f"Warnings: {summary.get('number_of_warnings') or 0}\n"
                f"Import-ID: {item.get('import_id') or '–'}\n"
                f"Kilde: {item.get('source_file') or item.get('source_path') or '–'}"
            )
            ctk.CTkLabel(
                frame,
                text=text,
                anchor="w",
                justify="left",
                wraplength=900,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(
                row=row_no,
                column=0,
                sticky="ew",
                padx=6,
                pady=7,
            )

            ctk.CTkButton(
                frame,
                text="Åpne testdekning",
                width=135,
                command=lambda selected=item: self._choose(selected),
            ).grid(
                row=row_no,
                column=1,
                padx=6,
                pady=7,
            )

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=18,
            pady=(0, 18),
        )
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

    def _choose(self, selected) -> None:
        self.destroy()
        self._open_import(
            self.work_operations,
            selected,
        )


class ExternalResultBankDialog(ctk.CTkToplevel):
    def __init__(self, master, *, bank: dict) -> None:
        super().__init__(master)
        self.title("Ressursbank – eksterne testresultater")
        self.geometry("1540x880")
        self.minsize(1080, 650)
        self.transient(master)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self,
            text="RESSURSBANK – EKSTERNE TESTRESULTATER",
            anchor="w",
            font=theme.font(theme.TITLE_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 4))

        summary = bank.get("summary") or {}
        groups = bank.get("groups") or []
        ctk.CTkLabel(
            self,
            text=(
                f"Eksterne rapporter/kjøringer: {len(groups)}  |  "
                f"Resultater totalt: {summary.get('resources', 0)}  |  "
                f"Bekrefter intern: {summary.get('corroborates_internal', 0)}  |  "
                f"Konflikt: {summary.get('conflicts_with_internal', 0)}  |  "
                f"Ikke kartlagt/ekstern: "
                f"{summary.get('external_only_or_unmapped', 0)}\n"
                "Hver ekstern rapport beholdes som egen kildegruppe. "
                "Resultatene erstatter ikke DWM-masterresultater."
            ),
            anchor="w",
            justify="left",
            wraplength=1480,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        outer = ctk.CTkScrollableFrame(self)
        outer.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 10))
        outer.grid_columnconfigure(0, weight=1)

        row_cursor = 0
        for group_no, group in enumerate(groups, start=1):
            group_summary = group.get("summary") or {}
            version = _display(group.get("source_version"))
            test_date = _display(group.get("source_test_date"))
            source_tests = group.get("source_number_of_tests")
            resources = group.get("resources") or []

            title = (
                f"{group_no}. {group.get('source_system') or 'Ekstern kilde'}"
                f"  |  versjon {version}"
                f"  |  testdato {test_date}"
                f"  |  {len(resources)} resultat(er)"
            )
            if source_tests not in (None, ""):
                title += f" / {source_tests} tester i kilderapport"

            ctk.CTkLabel(
                outer,
                text=title,
                anchor="w",
                justify="left",
                font=theme.font(theme.NORMAL_SIZE),
            ).grid(
                row=row_cursor,
                column=0,
                sticky="ew",
                padx=6,
                pady=(10 if row_cursor else 4, 2),
            )
            row_cursor += 1

            ctk.CTkLabel(
                outer,
                text=(
                    f"Import-ID: {_display(group.get('source_import_id'))}\n"
                    f"SHA-256: {_display(group.get('source_sha256'))}\n"
                    f"Kildefil: {_display(group.get('source_file'))}\n"
                    f"Bekrefter intern: {group_summary.get('corroborates_internal', 0)}  |  "
                    f"Konflikt: {group_summary.get('conflicts_with_internal', 0)}  |  "
                    f"Sammenligning ikke tilgjengelig: "
                    f"{group_summary.get('comparison_not_available', 0)}  |  "
                    f"Ekstern/ikke kartlagt: "
                    f"{group_summary.get('external_only_or_unmapped', 0)}"
                ),
                anchor="w",
                justify="left",
                wraplength=1460,
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(
                row=row_cursor,
                column=0,
                sticky="ew",
                padx=6,
                pady=(0, 6),
            )
            row_cursor += 1

            table = ctk.CTkFrame(outer)
            table.grid(
                row=row_cursor,
                column=0,
                sticky="ew",
                padx=6,
                pady=(0, 14),
            )
            for column, weight in enumerate((0, 2, 0, 0, 2)):
                table.grid_columnconfigure(column, weight=weight)

            headers = (
                "Test",
                "Navn",
                "Status",
                "Dekning",
                "Forhold til DWM",
            )
            for column, label in enumerate(headers):
                ctk.CTkLabel(
                    table,
                    text=label,
                    anchor="w",
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(
                    row=0,
                    column=column,
                    sticky="ew",
                    padx=6,
                    pady=(6, 8),
                )

            for item_no, item in enumerate(resources, start=1):
                values = (
                    item.get("test_id"),
                    item.get("test_name"),
                    item.get("status"),
                    _COVERAGE_LABELS.get(
                        item.get("coverage_classification"),
                        item.get("coverage_classification") or "–",
                    ),
                    _RELATION_LABELS.get(
                        item.get("relationship_to_internal"),
                        item.get("relationship_to_internal") or "–",
                    ),
                )
                for column, value in enumerate(values):
                    ctk.CTkLabel(
                        table,
                        text=str(value or "–"),
                        anchor="w",
                        justify="left",
                        wraplength=430 if column in (1, 4) else 210,
                        font=theme.font(theme.SMALL_SIZE),
                    ).grid(
                        row=item_no,
                        column=column,
                        sticky="new",
                        padx=6,
                        pady=3,
                    )

            row_cursor += 1

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
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


class DepotResultViewsDialogA13(DepotResultViewsDialogA12):
    def _build_external_evidence_tab(self, tab) -> None:
        super()._build_external_evidence_tab(tab)

        bank = ctk.CTkFrame(tab, fg_color="transparent")
        bank.grid(row=4, column=0, sticky="ew", padx=8, pady=(0, 8))
        bank.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            bank,
            text=(
                "Samle importerte eksterne testresultater i en kildeangitt "
                "ressursbank. Hver ekstern rapport/kjøring beholdes separat."
            ),
            anchor="w",
            justify="left",
            wraplength=720,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            bank,
            text="Ressursbank...",
            width=125,
            state="normal" if self.report_path else "disabled",
            command=self._open_external_result_bank,
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

        if len(imports) == 1:
            self._open_arkade5_coverage_for_import(
                work,
                imports[0],
            )
            return

        Arkade5CoverageSelectionDialog(
            self,
            work_operations=work,
            imports=imports,
            open_import=self._open_arkade5_coverage_for_import,
        )

    def _open_arkade5_coverage_for_import(self, work, selected) -> None:
        try:
            loaded = load_arkade5_import(
                work,
                str(selected.get("import_id")),
            )
            coverage = build_arkade5_coverage(loaded["normalized"])
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        summary = selected.get("source_summary") or {}
        label = (
            f"Arkade 5 {selected.get('import_id', '')} | "
            f"Testdato: {summary.get('date_of_testing') or '–'}"
        )
        Arkade5CoverageDialog(
            self,
            coverage=coverage,
            source_label=label,
        )

    def _open_external_result_bank(self) -> None:
        if self.report_path is None:
            return

        try:
            work = infer_work_operations_from_depot_report(self.report_path)
            path = write_external_result_bank(work)
            bank = build_external_result_bank(work)
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        if not bank.get("resources"):
            messagebox.showinfo(
                APP_NAME,
                "Ressursbanken er tom. Importer ekstern evidens først.",
                parent=self,
            )
            return

        self._last_external_result_bank = path
        ExternalResultBankDialog(self, bank=bank)
