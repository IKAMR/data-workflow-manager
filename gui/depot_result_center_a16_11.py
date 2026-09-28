from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_10 import DepotResultCenterDialogA16_10


class DepotResultCenterDialogA16_11(DepotResultCenterDialogA16_10):
    """a16.11: compact annual workspace and cleaner control overview."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._reorder_archive_tabs()
        if getattr(self, "_archive_parts", None):
            self._render_a166(self._archive_index)
            self._render_a169_controls(self._archive_index)

    def _reorder_archive_tabs(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None:
            return
        wanted = ["Sammendrag", "Per år", "Kontroller", "Vurderingspunkter"]
        try:
            current = list(getattr(tabs, "_name_list", []))
            ordered = [name for name in wanted if name in current]
            ordered.extend(name for name in current if name not in ordered)
            tabs._name_list = ordered
            segmented = getattr(tabs, "_segmented_button", None)
            if segmented is not None:
                segmented.configure(values=ordered)
        except Exception:
            pass

    def _render_a166(self, index: int) -> None:
        table = getattr(self, "_a166_table", None)
        if table is None:
            return
        for child in table.winfo_children():
            child.destroy()

        row = self._archive_parts[index]
        values = {key: self._series(row, key) for key, _label in self._SERIES}
        years = sorted({y for data in values.values() for y, n in data.items() if n > 0})
        headers = ("År", "Mapper/saker", "Registrering/JP", "Dok.beskr.", "Dok.objekter")
        widths = (58, 118, 128, 118, 118)
        for col, (label, width) in enumerate(zip(headers, widths)):
            table.grid_columnconfigure(col, weight=0, minsize=width)
            ctk.CTkLabel(table, text=label, anchor="e" if col else "w",
                         font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
                row=0, column=col, sticky="ew", padx=5, pady=(2, 4))
        if not years:
            ctk.CTkLabel(table, text="Ingen årsfordeling materialisert.", anchor="w",
                         text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE)).grid(
                row=1, column=0, columnspan=5, sticky="w", padx=5, pady=6)
            return

        keys = ("folder", "journal", "document_description", "document_object")
        totals = {key: 0 for key in keys}
        for r, year in enumerate(years, start=1):
            ctk.CTkLabel(table, text=str(year), anchor="w",
                         font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
                row=r, column=0, sticky="ew", padx=5, pady=1)
            for col, key in enumerate(keys, start=1):
                n = int(values[key].get(year, 0) or 0)
                totals[key] += n
                ctk.CTkLabel(table, text=f"{n:,}".replace(",", " "), anchor="e",
                             font=theme.font(theme.SMALL_SIZE)).grid(
                    row=r, column=col, sticky="ew", padx=5, pady=1)
        total_row = len(years) + 1
        ctk.CTkLabel(table, text="Sum", anchor="w",
                     font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
            row=total_row, column=0, sticky="ew", padx=5, pady=(4, 2))
        for col, key in enumerate(keys, start=1):
            ctk.CTkLabel(table, text=f"{totals[key]:,}".replace(",", " "), anchor="e",
                         font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
                row=total_row, column=col, sticky="ew", padx=5, pady=(4, 2))

    def _render_a169_controls(self, index: int) -> None:
        table = getattr(self, "_a168_controls_table", None)
        if table is None:
            return
        for child in table.winfo_children():
            child.destroy()

        mins = (165, 300, 95, 65, 165, 300, 95, 65)
        for col, width in enumerate(mins):
            table.grid_columnconfigure(col, weight=1 if col in (1, 5) else 0, minsize=width)

        cursor = 0
        for section in self._sections_for_index(index):
            section_label = str(section.get("label") or section.get("id") or "Kontroller")
            if section_label.strip().casefold() == "omfang per år":
                continue
            fields = list(section.get("fields") or [])
            ctk.CTkLabel(table, text=section_label, anchor="w",
                         font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(
                row=cursor, column=0, columnspan=8, sticky="ew", padx=7, pady=(6, 2))
            cursor += 1
            pair_col = 0
            for field in fields:
                shown = self._shown_value(field)
                source = field.get("source_test_id") or field.get("source_test") or "–"
                status = str(field.get("status") or "value_missing")
                wide = isinstance(field.get("value"), (dict, list)) or len(shown) > 90
                label = field.get("label") or field.get("id") or "Felt"
                if wide:
                    if pair_col:
                        cursor += 1
                        pair_col = 0
                    ctk.CTkLabel(table, text=str(label), anchor="w", font=theme.font(theme.SMALL_SIZE)).grid(
                        row=cursor, column=0, sticky="nw", padx=7, pady=1)
                    ctk.CTkLabel(table, text=shown, anchor="w", justify="left", wraplength=760,
                                 font=theme.font(theme.SMALL_SIZE)).grid(
                        row=cursor, column=1, columnspan=5, sticky="ew", padx=7, pady=1)
                    ctk.CTkLabel(table, text=str(source), anchor="w", text_color=theme.TEXT_SUB,
                                 font=theme.font(theme.SMALL_SIZE)).grid(row=cursor, column=6, sticky="nw", padx=7, pady=1)
                    ctk.CTkLabel(table, text="OK" if status == "ok" else status, anchor="w",
                                 text_color=theme.TEXT_SUB, font=theme.font(theme.SMALL_SIZE)).grid(
                        row=cursor, column=7, sticky="nw", padx=7, pady=1)
                    cursor += 1
                    continue
                base = 0 if pair_col == 0 else 4
                for col, text, anchor in ((base, label, "w"), (base + 1, shown, "w"),
                                          (base + 2, source, "w"),
                                          (base + 3, "OK" if status == "ok" else status, "w")):
                    ctk.CTkLabel(table, text=str(text), anchor=anchor,
                                 text_color=theme.TEXT_SUB if col in (base + 2, base + 3) else None,
                                 font=theme.font(theme.SMALL_SIZE)).grid(
                        row=cursor, column=col, sticky="ew" if col == base + 1 else "w", padx=7, pady=1)
                if pair_col == 0:
                    pair_col = 1
                else:
                    pair_col = 0
                    cursor += 1
            if pair_col:
                cursor += 1
        if cursor == 0:
            ctk.CTkLabel(table, text="Ingen materialiserte kontroller for valgt arkivdel.", anchor="w").grid(
                row=0, column=0, columnspan=8, sticky="ew", padx=7, pady=8)
