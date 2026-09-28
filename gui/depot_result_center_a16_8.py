from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_7 import DepotResultCenterDialogA16_7


class DepotResultCenterDialogA16_8(DepotResultCenterDialogA16_7):
    """a16.8: period control, structured archive controls and compact PRONOM."""

    def __init__(self, master, **kwargs) -> None:
        self._a168_controls_table = None
        super().__init__(master, **kwargs)
        self._install_a168_controls_table()
        self._compact_a168_pronom()
        if getattr(self, "_archive_parts", None):
            self._render_a168(self._archive_index)

    def _compact_a168_pronom(self) -> None:
        panel = getattr(self, "_a167_pronom_panel", None)
        if panel is None:
            return
        try:
            # Keep the table as a compact working table instead of stretching
            # Filtype across all unused widescreen space.
            panel.grid_columnconfigure(0, weight=0, minsize=1110)
            panel.grid_configure(sticky="nsw")
            for child in panel.winfo_children():
                info = child.grid_info()
                if str(info.get("row")) == "1":
                    child.configure(width=1110)
                    child.grid_configure(sticky="nsw")
        except Exception:
            pass

    def _install_a168_controls_table(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None:
            return
        try:
            tab = tabs.tab("Kontroller")
        except Exception:
            return

        old = getattr(self, "_a10_controls", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass

        table = ctk.CTkScrollableFrame(tab)
        table.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        tab.grid_rowconfigure(1, weight=1)
        widths = (220, 480, 150, 130)
        for col, width in enumerate(widths):
            table.grid_columnconfigure(col, weight=1 if col == 1 else 0, minsize=width)
        self._a168_controls_table = table

    @staticmethod
    def _span_tuple(span: dict | None) -> tuple[int | None, int | None]:
        span = span or {}
        return span.get("first_year"), span.get("last_year")

    @staticmethod
    def _period_status(reported, observed) -> str:
        if reported == (None, None):
            return "MANGLER OPPGITT YTTERÅR"
        if observed == (None, None):
            return "MANGLER OBSERVERT AKTIVITET"
        return "SAMSVAR" if reported == observed else "AVVIK"

    def _render_a168(self, index: int) -> None:
        self._render_a168_period(index)
        self._render_a168_controls(index)

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if self._a168_controls_table is not None:
            self._render_a168(index)

    def _render_a168_period(self, index: int) -> None:
        label = getattr(self, "_a164_period_text", None)
        if label is None:
            return
        row = self._archive_parts[index]
        reported, observed = self._periods(row)
        status = self._period_status(reported, observed)

        period = self._period_model()
        declared = period.get("declared_period") or {}
        extraction = (declared.get("start_year"), declared.get("end_year"))
        series = period.get("observed_series") or {}
        running = self._span_tuple((series.get("running_journal") or {}).get("span"))
        public = self._span_tuple((series.get("public_journal") or {}).get("span"))
        changes = self._span_tuple((series.get("change_log") or {}).get("span"))
        journal_match = (period.get("cross_checks") or {}).get("journal_year_distribution_match")
        cross = "SAMSVAR" if journal_match is True else ("AVVIK" if journal_match is False else "IKKE SAMMENLIGNET")

        label.configure(text=(
            f"Arkivdel: {status}   |   Oppgitt ytterår: {self._period_text(reported)}   |   "
            f"Observert aktivitet: {self._period_text(observed)}\n"
            f"Hele uttrekket oppgitt: {self._period_text(extraction)}   |   "
            f"Løpende journal: {self._period_text(running)}   |   "
            f"Offentlig journal: {self._period_text(public)}   |   "
            f"Endringslogg: {self._period_text(changes)}   |   Journal-krysskontroll: {cross}"
        ))

    def _render_a168_controls(self, index: int) -> None:
        table = self._a168_controls_table
        if table is None:
            return
        for child in table.winfo_children():
            child.destroy()

        headers = ("Kontroll / felt", "Resultat / verdi", "Kilde", "Status")
        for col, heading in enumerate(headers):
            ctk.CTkLabel(
                table, text=heading, anchor="w",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=0, column=col, sticky="ew", padx=7, pady=(5, 8))

        cursor = 1
        for section in self._sections_for_index(index):
            ctk.CTkLabel(
                table,
                text=str(section.get("label") or section.get("id") or "Kontroller"),
                anchor="w", font=theme.font(theme.NORMAL_SIZE, weight="bold"),
            ).grid(row=cursor, column=0, columnspan=4, sticky="ew", padx=7, pady=(9, 3))
            cursor += 1
            for field in section.get("fields") or []:
                status = str(field.get("status") or "value_missing")
                value = field.get("value")
                if isinstance(value, dict):
                    shown = ", ".join(f"{k}: {v}" for k, v in value.items()) or "–"
                elif isinstance(value, list):
                    shown = ", ".join(str(v) for v in value) or "–"
                else:
                    shown = "–" if value in (None, "") else str(value)
                source = field.get("source_test_id") or field.get("source_test") or "–"
                values = (
                    field.get("label") or field.get("id") or "Felt",
                    shown if status == "ok" else status,
                    source,
                    "OK" if status == "ok" else status,
                )
                for col, cell in enumerate(values):
                    ctk.CTkLabel(
                        table, text=str(cell), anchor="w", justify="left",
                        wraplength=460 if col == 1 else 210,
                        text_color=theme.TEXT_SUB if col in (2, 3) else None,
                        font=theme.font(theme.SMALL_SIZE),
                    ).grid(row=cursor, column=col, sticky="new", padx=7, pady=3)
                cursor += 1

        if cursor == 1:
            ctk.CTkLabel(table, text="Ingen materialiserte kontroller for valgt arkivdel.", anchor="w").grid(
                row=1, column=0, columnspan=4, sticky="ew", padx=7, pady=10)
