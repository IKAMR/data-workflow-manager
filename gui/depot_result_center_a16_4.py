from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a15_1 import DepotResultCenterDialogA15_1


class DepotResultCenterDialogA16_4(DepotResultCenterDialogA15_1):
    """a16.4: show materialized period reconciliation in archive-part summary."""

    def __init__(self, master, **kwargs) -> None:
        self._a164_period_panel = None
        self._a164_period_text = None
        self._a165_year_table = None
        super().__init__(master, **kwargs)
        self._replace_a15_chart_with_year_table()
        self._install_a164_period_panel()
        if getattr(self, "_archive_parts", None):
            self._render_a164_period(self._archive_index)
            self._render_a165_year_table(self._archive_index)

    def _install_a164_period_panel(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None:
            return
        try:
            tab = tabs.tab("Sammendrag")
        except Exception:
            return

        # Keep annual chart at row 3 and move inherited detail content one row down.
        for child in tab.winfo_children():
            if child is getattr(self, "_a15_year_panel", None):
                continue
            try:
                info = child.grid_info()
            except Exception:
                continue
            if str(info.get("row")) == "4":
                child.grid_configure(row=5)
        tab.grid_rowconfigure(4, weight=0)
        tab.grid_rowconfigure(5, weight=1)

        panel = ctk.CTkFrame(tab)
        panel.grid(row=4, column=0, sticky="ew", padx=4, pady=(0, 8))
        panel.grid_columnconfigure(0, weight=1)
        self._a164_period_panel = panel

        ctk.CTkLabel(
            panel,
            text="Periodeavstemming",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        self._a164_period_text = ctk.CTkLabel(
            panel,
            text="",
            anchor="w",
            justify="left",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a164_period_text.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 9))

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if self._a164_period_text is not None:
            self._render_a164_period(index)
        if self._a165_year_table is not None:
            self._render_a165_year_table(index)

    def _period_model(self) -> dict:
        model = getattr(self, "model", None) or getattr(self, "_model", None) or {}
        return model.get("period_reconciliation") or {}

    @staticmethod
    def _span_text(span: dict | None) -> str:
        span = span or {}
        first, last = span.get("first_year"), span.get("last_year")
        if not first and not last:
            return "–"
        if not first:
            return f"–{last}"
        if not last:
            return f"{first}–"
        return f"{first}–{last}"


    def _replace_a15_chart_with_year_table(self) -> None:
        panel = getattr(self, "_a15_year_panel", None)
        canvas = getattr(self, "_a15_year_canvas", None)
        if panel is None or canvas is None:
            return
        canvas.grid_forget()
        table = ctk.CTkScrollableFrame(panel, height=250)
        table.grid(row=1, column=0, sticky="nsew", padx=10, pady=(2, 9))
        panel.grid_rowconfigure(1, weight=1)
        self._a165_year_table = table

    def _render_a165_year_table(self, index: int) -> None:
        table = self._a165_year_table
        if table is None:
            return
        for child in table.winfo_children():
            child.destroy()
        row = self._archive_parts[index]
        values = {key: self._series(row, key) for key, _label in self._SERIES}
        years = sorted({year for series in values.values() for year, count in series.items() if count > 0})
        headers = ("År", "Mapper/saker", "Registrering/JP", "Dok.beskrivelser", "Dok.objekter")
        widths = (60, 125, 125, 145, 125)
        for col, (label, width) in enumerate(zip(headers, widths)):
            table.grid_columnconfigure(col, weight=1 if col else 0, minsize=width)
            ctk.CTkLabel(table, text=label, anchor="e" if col else "w",
                         font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
                row=0, column=col, sticky="ew", padx=6, pady=(4, 6))
        if not years:
            ctk.CTkLabel(table, text="Ingen årsfordeling materialisert.", anchor="w",
                         text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE)).grid(
                row=1, column=0, columnspan=5, sticky="ew", padx=6, pady=8)
            return
        keys = ("folder", "journal", "document_description", "document_object")
        for r, year in enumerate(years, start=1):
            ctk.CTkLabel(table, text=str(year), anchor="w", font=theme.font(theme.SMALL_SIZE)).grid(
                row=r, column=0, sticky="ew", padx=6, pady=2)
            for col, key in enumerate(keys, start=1):
                n = values[key].get(year, 0)
                ctk.CTkLabel(table, text=f"{n:,}".replace(",", " "), anchor="e",
                             font=theme.font(theme.SMALL_SIZE)).grid(
                    row=r, column=col, sticky="ew", padx=6, pady=2)

    def _render_a164_period(self, index: int) -> None:
        if self._a164_period_text is None:
            return
        period = self._period_model()
        if not period:
            self._a164_period_text.configure(text="Periodeavstemming er ikke materialisert i rapporten.")
            return

        declared = period.get("declared_period") or {}
        declared_text = "–"
        if declared.get("start_year") or declared.get("end_year"):
            declared_text = f"{declared.get('start_year') or '–'}–{declared.get('end_year') or '–'}"

        row = self._archive_parts[index]
        identity = row.get("archive_part") or {}
        key = str(identity.get("system_id") or identity.get("index") or "")
        part = next(
            (p for p in period.get("archive_parts") or []
             if str((p.get("archive_part") or {}).get("system_id") or (p.get("archive_part") or {}).get("index") or "") == key),
            {},
        )
        observed = self._span_text(part.get("observed_period"))

        series = period.get("observed_series") or {}
        running = self._span_text((series.get("running_journal") or {}).get("span"))
        public = self._span_text((series.get("public_journal") or {}).get("span"))
        changes = self._span_text((series.get("change_log") or {}).get("span"))
        journal_match = (period.get("cross_checks") or {}).get("journal_year_distribution_match")
        cross = "journaler samsvarer" if journal_match is True else ("journaler avviker" if journal_match is False else "journaler ikke sammenlignet")

        self._a164_period_text.configure(text=(
            f"Oppgitt i arkivuttrekk.xml: {declared_text}   |   "
            f"Arkivdel observert: {observed}\n"
            f"Løpende journal: {running}   |   Offentlig journal: {public}   |   "
            f"Endringslogg: {changes}   |   Krysskontroll: {cross}"
        ))
