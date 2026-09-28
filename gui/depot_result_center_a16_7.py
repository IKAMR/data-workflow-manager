from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_6 import DepotResultCenterDialogA16_6
from .depot_result_views_a29 import _missing_archive_fields
from .depot_result_views_a22 import _identity


class DepotResultCenterDialogA16_7(DepotResultCenterDialogA16_6):
    """a16.7: compact archive-part workspace and readable PRONOM columns."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._compact_archive_workspace()
        tabs = self._root_tabview()
        if tabs is not None:
            self._replace_pronom_text_with_table(tabs.tab("Filformater"))
        self._refresh_a167_archive_cards()

    def _compact_archive_workspace(self) -> None:
        dashboard = getattr(self, "_a11_dashboard", None)
        if dashboard is not None:
            try:
                dashboard.grid_configure(padx=8, pady=(4, 4))
            except Exception:
                pass
            chart = getattr(self, "_a11_chart", None)
            if chart is not None:
                try:
                    chart.configure(height=66)
                except Exception:
                    pass

        tabs = getattr(self, "_a10_tabs", None)
        if tabs is not None:
            try:
                tabs.grid_configure(padx=8, pady=(0, 6))
                summary = tabs.tab("Sammendrag")
                for child in summary.winfo_children():
                    try:
                        info = child.grid_info()
                        row = int(info.get("row", -1))
                        if row in (0, 1, 2):
                            child.grid_configure(pady=(2, 4))
                    except Exception:
                        pass
            except Exception:
                pass

        nav = getattr(self, "_archive_navigation", None)
        if nav is not None:
            try:
                nav.configure(width=320)
            except Exception:
                pass

    def _refresh_a167_archive_cards(self) -> None:
        for index, button in enumerate(getattr(self, "_archive_buttons", [])):
            row = self._archive_parts[index]
            system_id, title = _identity(row, index)
            missing = _missing_archive_fields(row)
            reported, observed = self._periods(row)
            data = f"Mangler {len(missing)}" if missing else "Komplett"
            period = f"obs. {self._period_text(observed)}"
            if reported != (None, None):
                period = f"{self._period_text(reported)} / {period}"
            button.configure(
                text=f"{title}\n{system_id}\n{data}  |  {period}",
                height=66,
            )

    def _replace_pronom_text_with_table(self, tab) -> None:
        old = getattr(self, "_a14_pronom_text", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass
        old_panel = getattr(self, "_a167_pronom_panel", None)
        if old_panel is not None:
            try:
                old_panel.destroy()
            except Exception:
                pass

        tab.grid_rowconfigure(1, weight=1)
        panel = ctk.CTkFrame(tab, fg_color="transparent")
        panel.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        self._a167_pronom_panel = panel

        arkade = ((self.model.get("external_validation") or {}).get("arkade5") or {})
        summary = arkade.get("pronom_summary") or {}
        imports = list(arkade.get("imports") or [])
        ctk.CTkLabel(
            panel,
            text=(
                f"Statistikksett: {summary.get('statistics_imports', 0)}   |   "
                f"Rader: {summary.get('statistics_rows', 0)}   |   "
                f"Filer: {summary.get('total_files', 0)}   |   "
                f"Unike Format-ID: {summary.get('unique_format_ids', 0)}"
            ),
            anchor="w", text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        table = ctk.CTkScrollableFrame(panel)
        table.grid(row=1, column=0, sticky="nsew")
        headers = ("Format-ID / PUID", "Filtype", "Formatversjon", "RAF-220301", "Antall")
        # Fixed, adjacent working widths. Only Filtype grows moderately; the
        # three right-hand columns no longer drift to the far screen edge.
        mins = (125, 520, 150, 145, 100)
        for col, (heading, minsize) in enumerate(zip(headers, mins)):
            table.grid_columnconfigure(col, weight=1 if col == 1 else 0, minsize=minsize)
            ctk.CTkLabel(
                table, text=heading, anchor="w" if col < 4 else "e",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=0, column=col, sticky="ew", padx=6, pady=(4, 7))

        row_no = 1
        for item in imports:
            pronom = item.get("pronom") or {}
            if not pronom.get("available"):
                continue
            stats = pronom.get("statistics") or {}
            for data in list(stats.get("rows") or []):
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
