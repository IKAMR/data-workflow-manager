from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_views_a15 import DepotResultViewsDialogA15


_STATUS_LABELS = {
    "covered_by_both": "DWM + Arkade",
    "covered_by_arkade": "Arkade dekker",
    "covered_by_dwm": "DWM dekker",
    "not_covered_in_run": "Ikke dekket i kjøringen",
}

_RELATION_LABELS = {
    "equivalent": "Ekvivalent",
    "partial": "Delvis overlapp",
    "complementary": "Komplementær",
    "arkade_only": "Kun Arkade",
}


def _display(value) -> str:
    return "–" if value in (None, "") else str(value)


class Arkade5CombinedCoverageDialog(ctk.CTkToplevel):
    """Show combined DWM/Arkade coverage already materialized in the depot report."""

    def __init__(self, master, *, report_model: dict) -> None:
        super().__init__(master)
        self.title("Samlet DWM / Arkade 5-dekning")
        self.geometry("1600x900")
        self.minsize(1120, 680)
        self.transient(master)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        external = (report_model.get("external_validation") or {}).get("arkade5") or {}
        summary = external.get("summary") or {}
        imports = external.get("imports") or []

        ctk.CTkLabel(
            self,
            text="SAMLET DWM / ARKADE 5-DEKNING",
            anchor="w",
            font=theme.font(theme.TITLE_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 4))

        ctk.CTkLabel(
            self,
            text=(
                f"Arkade-kjøringer: {summary.get('imports', 0)}  |  "
                f"Dekket av Arkade: {summary.get('covered_by_arkade', 0)}  |  "
                f"Arkade-feil: {summary.get('arkade_errors', 0)}  |  "
                f"Arkade-advarsler: {summary.get('arkade_warnings', 0)}\n"
                "Visningen viser deknings- og evidensstatus. Arkade-resultater beholdes som "
                "ekstern evidens og blir ikke gjort om til DWM-masterresultater eller automatisk depotkonklusjon."
            ),
            anchor="w",
            justify="left",
            wraplength=1540,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        outer = ctk.CTkScrollableFrame(self)
        outer.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 10))
        outer.grid_columnconfigure(0, weight=1)

        if not imports:
            ctk.CTkLabel(
                outer,
                text="Ingen Arkade 5-evidens er materialisert i denne depotrapporten.",
                anchor="w",
                font=theme.font(theme.NORMAL_SIZE),
            ).grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        else:
            row_cursor = 0
            for import_no, item in enumerate(imports, start=1):
                coverage = item.get("coverage") or {}
                cov_summary = coverage.get("summary") or {}
                source = item.get("source") or {}

                ctk.CTkLabel(
                    outer,
                    text=(
                        f"{import_no}. Arkade 5  |  versjon {_display(item.get('source_version'))}  |  "
                        f"testdato {_display(item.get('date_of_testing'))}  |  "
                        f"import-ID {_display(item.get('import_id'))}"
                    ),
                    anchor="w",
                    justify="left",
                    font=theme.font(theme.SECTION_SIZE, "bold"),
                ).grid(row=row_cursor, column=0, sticky="ew", padx=6, pady=(10 if row_cursor else 4, 2))
                row_cursor += 1

                ctk.CTkLabel(
                    outer,
                    text=(
                        f"Kildefil: {_display(source.get('original_name'))}  |  SHA-256: {_display(source.get('sha256'))}\n"
                        f"Begge: {cov_summary.get('covered_by_both', 0)}  |  "
                        f"Arkade: {cov_summary.get('covered_by_arkade', 0)}  |  "
                        f"DWM: {cov_summary.get('covered_by_dwm', 0)}  |  "
                        f"Ikke dekket: {cov_summary.get('not_covered_in_run', 0)}  |  "
                        f"Arkade-feil: {cov_summary.get('arkade_errors', 0)}  |  "
                        f"Arkade-advarsler: {cov_summary.get('arkade_warnings', 0)}"
                    ),
                    anchor="w",
                    justify="left",
                    wraplength=1520,
                    text_color=theme.TEXT_MUTED,
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=row_cursor, column=0, sticky="ew", padx=6, pady=(0, 6))
                row_cursor += 1

                table = ctk.CTkFrame(outer)
                table.grid(row=row_cursor, column=0, sticky="ew", padx=6, pady=(0, 14))
                for column, weight in enumerate((0, 2, 0, 0, 2, 0)):
                    table.grid_columnconfigure(column, weight=weight)

                headers = ("Arkade", "Kontroll", "Relasjon", "Dekning", "DWM-test(er)", "Arkade-status")
                for column, label in enumerate(headers):
                    ctk.CTkLabel(
                        table,
                        text=label,
                        anchor="w",
                        font=theme.font(theme.SMALL_SIZE),
                    ).grid(row=0, column=column, sticky="ew", padx=6, pady=(6, 8))

                rows = coverage.get("arkade_control_areas") or []
                for item_no, control in enumerate(rows, start=1):
                    arkade = control.get("arkade") or {}
                    values = (
                        control.get("arkade_test_id"),
                        control.get("arkade_test_name"),
                        _RELATION_LABELS.get(control.get("relation"), control.get("relation") or "–"),
                        _STATUS_LABELS.get(control.get("combined_status"), control.get("combined_status") or "–"),
                        ", ".join(control.get("dwm_test_ids_present") or control.get("dwm_test_ids") or []) or "–",
                        arkade.get("status") or "–",
                    )
                    for column, value in enumerate(values):
                        ctk.CTkLabel(
                            table,
                            text=str(value or "–"),
                            anchor="w",
                            justify="left",
                            wraplength=420 if column in (1, 4) else 230,
                            font=theme.font(theme.SMALL_SIZE),
                        ).grid(row=item_no, column=column, sticky="new", padx=6, pady=3)

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


class DepotResultViewsDialogA16(DepotResultViewsDialogA15):
    """v0.1.5-a6: expose materialized combined DWM/Arkade coverage in GUI."""

    def _build_external_evidence_tab(self, tab) -> None:
        super()._build_external_evidence_tab(tab)

        combined = ctk.CTkFrame(tab, fg_color="transparent")
        combined.grid(row=7, column=0, sticky="ew", padx=8, pady=(0, 8))
        combined.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            combined,
            text=(
                "Vis samlet dekningsstatus fra depotrapporten: hvilke Noark 5-kontrollområder "
                "som er dekket av DWM, Arkade 5 eller begge, og hvor Arkade tetter DWM-hull."
            ),
            anchor="w",
            justify="left",
            wraplength=720,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        has_external = bool(((self.model.get("external_validation") or {}).get("arkade5") or {}).get("imports"))
        ctk.CTkButton(
            combined,
            text="Samlet DWM/Arkade-dekning...",
            width=205,
            state="normal" if has_external else "disabled",
            command=self._open_combined_arkade5_coverage,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)

    def _open_combined_arkade5_coverage(self) -> None:
        Arkade5CombinedCoverageDialog(self, report_model=self.model)
