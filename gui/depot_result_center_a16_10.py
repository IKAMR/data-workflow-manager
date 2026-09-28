from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_9 import DepotResultCenterDialogA16_9


class DepotResultCenterDialogA16_10(DepotResultCenterDialogA16_9):
    """a16.10: separate annual workspace and sortable PRONOM table."""

    def __init__(self, master, **kwargs) -> None:
        self._a1610_pronom_rows = []
        self._a1610_pronom_sort = ("count", True)
        super().__init__(master, **kwargs)
        self._install_per_year_tab()
        self._rebuild_pronom_table()

    def _install_per_year_tab(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        panel = getattr(self, "_a15_year_panel", None)
        if tabs is None or panel is None:
            return
        try:
            tabs.add("Per år")
            tab = tabs.tab("Per år")
        except Exception:
            return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        try:
            panel.grid_forget()
            panel.configure(master=tab)
        except Exception:
            # Tk widgets cannot normally change master. Recreate a host and move
            # the annual table widget itself when that is the case.
            host = ctk.CTkFrame(tab)
            host.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
            host.grid_columnconfigure(0, weight=1)
            host.grid_rowconfigure(1, weight=1)
            ctk.CTkLabel(host, text="Omfang per år", anchor="w",
                         font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(
                row=0, column=0, sticky="ew", padx=10, pady=(8, 3))
            old_table = getattr(self, "_a166_table", None)
            if old_table is not None:
                try:
                    old_table.grid_forget()
                except Exception:
                    pass
            table = ctk.CTkScrollableFrame(host)
            table.grid(row=1, column=0, sticky="nsew", padx=10, pady=(2, 9))
            self._a166_table = table
            self._a15_year_panel = host
            if getattr(self, "_archive_parts", None):
                self._render_a166(self._archive_index)
            return
        panel.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        try:
            panel.grid_rowconfigure(1, weight=1)
            self._a166_table.configure(height=520)
        except Exception:
            pass

    def _collect_pronom_rows(self):
        rows = []
        arkade = ((self.model.get("external_validation") or {}).get("arkade5") or {})
        for item in list(arkade.get("imports") or []):
            pronom = item.get("pronom") or {}
            if not pronom.get("available"):
                continue
            rows.extend(list((pronom.get("statistics") or {}).get("rows") or []))
        return rows

    @staticmethod
    def _pronom_value(row, key):
        if key == "count":
            try:
                return int(row.get("count") or 0)
            except Exception:
                return 0
        return str(row.get(key) or "").casefold()

    def _sort_pronom(self, key: str) -> None:
        current_key, descending = self._a1610_pronom_sort
        if key == current_key:
            descending = not descending
        else:
            descending = key == "count"
        self._a1610_pronom_sort = (key, descending)
        self._render_pronom_rows()

    def _rebuild_pronom_table(self) -> None:
        panel = getattr(self, "_a167_pronom_panel", None)
        if panel is None:
            return
        for child in list(panel.winfo_children()):
            try:
                if int(child.grid_info().get("row", -1)) == 1:
                    child.destroy()
            except Exception:
                pass
        panel.grid_configure(sticky="nsew")
        panel.grid_columnconfigure(0, weight=1, minsize=0)
        holder = ctk.CTkFrame(panel, fg_color="transparent", width=1120)
        holder.grid(row=1, column=0, sticky="nsw")
        holder.grid_propagate(False)
        holder.grid_rowconfigure(0, weight=1)
        holder.grid_columnconfigure(0, weight=1)
        table = ctk.CTkScrollableFrame(holder, width=1100)
        table.grid(row=0, column=0, sticky="nsew")
        self._a169_pronom_table = table
        self._a1610_pronom_rows = self._collect_pronom_rows()
        self._render_pronom_rows()

    def _render_pronom_rows(self) -> None:
        table = getattr(self, "_a169_pronom_table", None)
        if table is None:
            return
        for child in table.winfo_children():
            child.destroy()
        specs = (
            ("format_id", "Format-ID / PUID", 130),
            ("file_type", "Filtype", 520),
            ("format_version", "Formatversjon", 150),
            ("raf_220301", "RAF-220301", 145),
            ("count", "Antall", 105),
        )
        active_key, descending = self._a1610_pronom_sort
        for col, (key, heading, width) in enumerate(specs):
            table.grid_columnconfigure(col, weight=0, minsize=width)
            marker = " ▼" if key == active_key and descending else (" ▲" if key == active_key else "")
            ctk.CTkButton(
                table, text=heading + marker, anchor="e" if key == "count" else "w",
                fg_color="transparent", hover_color=("gray75", "gray25"),
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
                command=lambda k=key: self._sort_pronom(k),
            ).grid(row=0, column=col, sticky="ew", padx=3, pady=(2, 5))
        rows = sorted(
            self._a1610_pronom_rows,
            key=lambda row: self._pronom_value(row, active_key),
            reverse=descending,
        )
        for row_no, data in enumerate(rows, start=1):
            values = (
                data.get("format_id") or "–", data.get("file_type") or "–",
                data.get("format_version") or "–", data.get("raf_220301") or "–",
                data.get("count") if data.get("count") is not None else "–",
            )
            for col, value in enumerate(values):
                ctk.CTkLabel(table, text=str(value), anchor="e" if col == 4 else "w",
                             justify="left", font=theme.font(theme.SMALL_SIZE)).grid(
                    row=row_no, column=col, sticky="ew", padx=6, pady=2)
        if not rows:
            ctk.CTkLabel(table, text="Ingen PRONOM-statistikk er materialisert i depotrapporten.",
                         anchor="w", text_color=theme.TEXT_MUTED,
                         font=theme.font(theme.SMALL_SIZE)).grid(
                row=1, column=0, columnspan=5, sticky="ew", padx=6, pady=8)
