from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_17 import DepotResultCenterDialogA16_17


class DepotResultCenterDialogA16_19(DepotResultCenterDialogA16_17):
    """a16.19: compact archive summary with dashboard moved to the heading area."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._move_dashboard_up()
        self._replace_summary_kpis()
        self._compact_summary_rows()
        if getattr(self, "_archive_parts", None):
            self._show_archive_part(getattr(self, "_archive_index", 0))

    def _move_dashboard_up(self) -> None:
        dashboard = getattr(self, "_a11_dashboard", None)
        detail = getattr(self, "_detail", None)
        if dashboard is None or detail is None:
            return
        try:
            # Keep the dashboard, but use the otherwise sparse top area.  The
            # archive title/subtitle and tab surface move down one compact row.
            dashboard.grid_configure(row=0, padx=16, pady=(4, 4))
            dashboard.configure(height=104)
            for widget_name in ("_archive_title", "_archive_subtitle", "_a10_tabs"):
                widget = getattr(self, widget_name, None)
                if widget is None:
                    continue
                info = widget.grid_info()
                row = int(info.get("row", 0))
                if row < 2:
                    widget.grid_configure(row=row + 1)
        except Exception:
            pass

        chart = getattr(self, "_a11_chart", None)
        if chart is not None:
            try:
                chart.configure(height=62)
            except Exception:
                pass

        # Tighten dashboard cards/status vertically.
        cards = getattr(self, "_a11_cards", {}) or {}
        for value in cards.values():
            try:
                value.grid_configure(pady=(4, 0))
                for sibling in value.master.winfo_children():
                    if sibling is not value:
                        sibling.grid_configure(pady=(0, 4))
            except Exception:
                pass

    def _replace_summary_kpis(self) -> None:
        labels = getattr(self, "_a10_kpi_labels", None)
        if not isinstance(labels, dict) or not labels:
            return
        try:
            frame = next(iter(labels.values())).master.master
            for child in frame.winfo_children():
                child.destroy()
            for col in range(3):
                frame.grid_columnconfigure(col, weight=1)
            frame.grid_configure(pady=(2, 4))

            self._a1618_pair_values = {}
            specs = (
                ("folder_count", "case_folder_count", "Mapper / saker"),
                ("registration_count", "journalpost_count", "Registreringer / JP"),
                ("document_description_count", "document_object_count", "Dok.beskrivelser / objekter"),
            )
            for col, (left, right, title) in enumerate(specs):
                card = ctk.CTkFrame(frame)
                card.grid(row=0, column=col, sticky="nsew", padx=3)
                value = ctk.CTkLabel(card, text="– / –", font=theme.font(theme.TITLE_SIZE, weight="bold"))
                value.grid(row=0, column=0, padx=10, pady=(5, 0))
                ctk.CTkLabel(card, text=title, text_color=theme.TEXT_MUTED,
                             font=theme.font(theme.SMALL_SIZE)).grid(row=1, column=0, padx=10, pady=(0, 5))
                self._a1618_pair_values[(left, right)] = value
            self._a10_kpi_labels = {}
        except Exception:
            self._a1618_pair_values = {}

    @staticmethod
    def _n(value) -> str:
        try:
            return f"{int(value or 0):,}".replace(",", " ")
        except (TypeError, ValueError):
            return "–"

    def _refresh_pair_kpis(self, index: int) -> None:
        if not getattr(self, "_a1618_pair_values", None) or not getattr(self, "_archive_parts", None):
            return
        row = self._archive_parts[index]
        for (left, right), label in self._a1618_pair_values.items():
            # case_folder_count is not yet guaranteed in every report.  Showing
            # dash rather than copying folder_count preserves the distinction.
            label.configure(text=f"{self._n(row.get(left))} / {self._n(row.get(right)) if row.get(right) is not None else '–'}")

    def _compact_summary_rows(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None:
            return
        try:
            tab = tabs.tab("Sammendrag")
            status = getattr(self, "_a10_data_status", None)
            if status is not None:
                status.master.grid_configure(pady=(0, 3))
                for child in status.master.winfo_children():
                    child.grid_configure(pady=4)
            treatment = getattr(self, "_a11_treatment_status", None)
            if treatment is not None:
                treatment.master.grid_configure(pady=(0, 3))
                for child in treatment.master.winfo_children():
                    child.grid_configure(pady=4)
            for row in range(0, 8):
                tab.grid_rowconfigure(row, weight=0)
            tab.grid_rowconfigure(6, weight=1)
        except Exception:
            pass

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._refresh_pair_kpis(index)
