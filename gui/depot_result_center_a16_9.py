from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_8 import DepotResultCenterDialogA16_8


class DepotResultCenterDialogA16_9(DepotResultCenterDialogA16_8):
    """a16.9: visible period reconciliation, compact controls and stable PRONOM table."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._place_period_before_years()
        self._rebuild_pronom_table()
        if getattr(self, "_archive_parts", None):
            self._render_a169_controls(self._archive_index)
            self._render_a168_period(self._archive_index)

    def _place_period_before_years(self) -> None:
        """Put period reconciliation where it is visible before the annual table."""
        period = getattr(self, "_a164_period_panel", None)
        years = getattr(self, "_a15_year_panel", None)
        if period is None or years is None:
            return
        try:
            years.grid_configure(row=4, pady=(0, 8))
            period.grid_configure(row=3, pady=(0, 8))
            parent = period.master
            parent.grid_rowconfigure(3, weight=0)
            parent.grid_rowconfigure(4, weight=1)
        except Exception:
            pass

    def _rebuild_pronom_table(self) -> None:
        panel = getattr(self, "_a167_pronom_panel", None)
        if panel is None:
            return
        # a16.8 tried to constrain the complete panel. Rebuild the table body
        # instead: fixed adjacent columns, left aligned, while the page itself
        # still uses the full result-window width.
        children = list(panel.winfo_children())
        for child in children:
            try:
                if int(child.grid_info().get("row", -1)) == 1:
                    child.destroy()
            except Exception:
                pass
        try:
            panel.grid_configure(sticky="nsew")
            panel.grid_columnconfigure(0, weight=1, minsize=0)
        except Exception:
            pass

        holder = ctk.CTkFrame(panel, fg_color="transparent", width=1120)
        holder.grid(row=1, column=0, sticky="nsw")
        holder.grid_propagate(False)
        holder.grid_rowconfigure(0, weight=1)
        holder.grid_columnconfigure(0, weight=1)

        table = ctk.CTkScrollableFrame(holder, width=1100)
        table.grid(row=0, column=0, sticky="nsew")
        headers = ("Format-ID / PUID", "Filtype", "Formatversjon", "RAF-220301", "Antall")
        widths = (130, 520, 150, 145, 105)
        for col, (heading, width) in enumerate(zip(headers, widths)):
            table.grid_columnconfigure(col, weight=0, minsize=width)
            ctk.CTkLabel(
                table, text=heading, anchor="e" if col == 4 else "w",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=0, column=col, sticky="ew", padx=6, pady=(4, 7))

        arkade = ((self.model.get("external_validation") or {}).get("arkade5") or {})
        row_no = 1
        for item in list(arkade.get("imports") or []):
            pronom = item.get("pronom") or {}
            if not pronom.get("available"):
                continue
            for data in list((pronom.get("statistics") or {}).get("rows") or []):
                values = (
                    data.get("format_id") or "–",
                    data.get("file_type") or "–",
                    data.get("format_version") or "–",
                    data.get("raf_220301") or "–",
                    data.get("count") if data.get("count") is not None else "–",
                )
                for col, value in enumerate(values):
                    ctk.CTkLabel(
                        table, text=str(value), anchor="e" if col == 4 else "w",
                        justify="left", font=theme.font(theme.SMALL_SIZE),
                    ).grid(row=row_no, column=col, sticky="ew", padx=6, pady=2)
                row_no += 1
        if row_no == 1:
            ctk.CTkLabel(
                table, text="Ingen PRONOM-statistikk er materialisert i depotrapporten.",
                anchor="w", text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, columnspan=5, sticky="ew", padx=6, pady=8)
        self._a169_pronom_table = table

    @staticmethod
    def _shown_value(field: dict) -> str:
        status = str(field.get("status") or "value_missing")
        value = field.get("value")
        if status != "ok":
            return status
        if isinstance(value, dict):
            return "  ·  ".join(f"{k}: {v}" for k, v in value.items()) or "–"
        if isinstance(value, list):
            return "  ·  ".join(str(v) for v in value) or "–"
        return "–" if value in (None, "") else str(value)

    def _render_a168_controls(self, index: int) -> None:
        # Override a16.8 renderer. Short controls are packed two per row;
        # wide distributions get one compact full-width row.
        self._render_a169_controls(index)

    def _render_a169_controls(self, index: int) -> None:
        table = getattr(self, "_a168_controls_table", None)
        if table is None:
            return
        for child in table.winfo_children():
            child.destroy()

        # Two compact field groups across the available work surface.
        mins = (165, 300, 95, 65, 165, 300, 95, 65)
        for col, width in enumerate(mins):
            table.grid_columnconfigure(col, weight=1 if col in (1, 5) else 0, minsize=width)

        cursor = 0
        for section in self._sections_for_index(index):
            fields = list(section.get("fields") or [])
            ctk.CTkLabel(
                table, text=str(section.get("label") or section.get("id") or "Kontroller"),
                anchor="w", font=theme.font(theme.NORMAL_SIZE, weight="bold"),
            ).grid(row=cursor, column=0, columnspan=8, sticky="ew", padx=7, pady=(7, 3))
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
                    ctk.CTkLabel(table, text=str(label), anchor="w",
                                 font=theme.font(theme.SMALL_SIZE)).grid(
                        row=cursor, column=0, sticky="nw", padx=7, pady=2)
                    ctk.CTkLabel(table, text=shown, anchor="w", justify="left", wraplength=760,
                                 font=theme.font(theme.SMALL_SIZE)).grid(
                        row=cursor, column=1, columnspan=5, sticky="ew", padx=7, pady=2)
                    ctk.CTkLabel(table, text=str(source), anchor="w", text_color=theme.TEXT_SUB,
                                 font=theme.font(theme.SMALL_SIZE)).grid(
                        row=cursor, column=6, sticky="nw", padx=7, pady=2)
                    ctk.CTkLabel(table, text="OK" if status == "ok" else status, anchor="w",
                                 text_color=theme.TEXT_SUB, font=theme.font(theme.SMALL_SIZE)).grid(
                        row=cursor, column=7, sticky="nw", padx=7, pady=2)
                    cursor += 1
                    continue

                base = 0 if pair_col == 0 else 4
                ctk.CTkLabel(table, text=str(label), anchor="w",
                             font=theme.font(theme.SMALL_SIZE)).grid(
                    row=cursor, column=base, sticky="w", padx=7, pady=2)
                ctk.CTkLabel(table, text=shown, anchor="w", justify="left", wraplength=285,
                             font=theme.font(theme.SMALL_SIZE)).grid(
                    row=cursor, column=base + 1, sticky="ew", padx=7, pady=2)
                ctk.CTkLabel(table, text=str(source), anchor="w", text_color=theme.TEXT_SUB,
                             font=theme.font(theme.SMALL_SIZE)).grid(
                    row=cursor, column=base + 2, sticky="w", padx=7, pady=2)
                ctk.CTkLabel(table, text="OK" if status == "ok" else status, anchor="w",
                             text_color=theme.TEXT_SUB, font=theme.font(theme.SMALL_SIZE)).grid(
                    row=cursor, column=base + 3, sticky="w", padx=7, pady=2)
                if pair_col == 0:
                    pair_col = 1
                else:
                    pair_col = 0
                    cursor += 1
            if pair_col:
                cursor += 1

        if cursor == 0:
            ctk.CTkLabel(table, text="Ingen materialiserte kontroller for valgt arkivdel.", anchor="w").grid(
                row=0, column=0, columnspan=8, sticky="ew", padx=7, pady=10)
