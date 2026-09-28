from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_4 import DepotResultCenterDialogA16_4


class DepotResultCenterDialogA16_6(DepotResultCenterDialogA16_4):
    """a16.6: readable annual counts and document-analysis placeholders."""

    def __init__(self, master, **kwargs) -> None:
        self._a166_table = None
        self._a166_doc_text = None
        super().__init__(master, **kwargs)
        self._install_a166_year_table()
        self._install_a166_document_panel()
        if getattr(self, "_archive_parts", None):
            self._render_a166(self._archive_index)

    def _install_a166_year_table(self) -> None:
        panel = getattr(self, "_a15_year_panel", None)
        if panel is None:
            return
        # Remove every inherited chart/table body. Keep the heading row only.
        for child in list(panel.winfo_children()):
            try:
                if int(child.grid_info().get("row", -1)) == 1:
                    child.destroy()
            except Exception:
                pass
        table = ctk.CTkScrollableFrame(panel, height=300)
        table.grid(row=1, column=0, sticky="nsew", padx=10, pady=(2, 9))
        panel.grid_rowconfigure(1, weight=1)
        self._a166_table = table
        # Prevent inherited redraw from drawing an invisible/obsolete canvas.
        self._a15_year_canvas = None
        self._a165_year_table = None

    def _install_a166_document_panel(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None:
            return
        try:
            tab = tabs.tab("Sammendrag")
        except Exception:
            return
        # Place directly below period reconciliation, before inherited details.
        for child in tab.winfo_children():
            if child in {getattr(self, "_a15_year_panel", None), getattr(self, "_a164_period_panel", None)}:
                continue
            try:
                if str(child.grid_info().get("row")) == "5":
                    child.grid_configure(row=6)
            except Exception:
                pass
        tab.grid_rowconfigure(5, weight=0)
        tab.grid_rowconfigure(6, weight=1)
        panel = ctk.CTkFrame(tab)
        panel.grid(row=5, column=0, sticky="ew", padx=4, pady=(0, 8))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="Dokumentanalyse", anchor="w",
                     font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        self._a166_doc_text = ctk.CTkLabel(
            panel, anchor="w", justify="left", text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
            text=("Neste datagrunnlag: dokumentbeskrivelse ↔ dokumentobjekt · hoveddokument ↔ vedlegg · "
                  "produksjonsformat ↔ arkivformat · dokumentnummer · versjonsnummer."),
        )
        self._a166_doc_text.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 9))

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if self._a166_table is not None:
            self._render_a166(index)

    def _render_a166(self, index: int) -> None:
        table = self._a166_table
        if table is None:
            return
        for child in table.winfo_children():
            child.destroy()
        row = self._archive_parts[index]
        values = {key: self._series(row, key) for key, _label in self._SERIES}
        years = sorted({y for data in values.values() for y, n in data.items() if n > 0})
        headers = ("År", "Mapper/saker", "Registrering/JP", "Dok.beskrivelser", "Dok.objekter")
        widths = (70, 145, 155, 170, 150)
        for col, (label, width) in enumerate(zip(headers, widths)):
            table.grid_columnconfigure(col, weight=1 if col else 0, minsize=width)
            ctk.CTkLabel(table, text=label, anchor="e" if col else "w",
                         font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
                row=0, column=col, sticky="ew", padx=8, pady=(5, 7))
        if not years:
            ctk.CTkLabel(table, text="Ingen årsfordeling materialisert.", anchor="w",
                         text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE)).grid(
                row=1, column=0, columnspan=5, sticky="ew", padx=8, pady=10)
            return
        keys = ("folder", "journal", "document_description", "document_object")
        totals = {key: 0 for key in keys}
        for r, year in enumerate(years, start=1):
            ctk.CTkLabel(table, text=str(year), anchor="w",
                         font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
                row=r, column=0, sticky="ew", padx=8, pady=3)
            for col, key in enumerate(keys, start=1):
                n = int(values[key].get(year, 0) or 0)
                totals[key] += n
                ctk.CTkLabel(table, text=f"{n:,}".replace(",", " "), anchor="e",
                             font=theme.font(theme.SMALL_SIZE)).grid(
                    row=r, column=col, sticky="ew", padx=8, pady=3)
        total_row = len(years) + 1
        ctk.CTkLabel(table, text="Sum", anchor="w",
                     font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
            row=total_row, column=0, sticky="ew", padx=8, pady=(8, 4))
        for col, key in enumerate(keys, start=1):
            ctk.CTkLabel(table, text=f"{totals[key]:,}".replace(",", " "), anchor="e",
                         font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
                row=total_row, column=col, sticky="ew", padx=8, pady=(8, 4))
