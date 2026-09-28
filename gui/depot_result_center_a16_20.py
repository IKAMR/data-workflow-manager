from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_19 import DepotResultCenterDialogA16_19
from .depot_result_views_a29 import _missing_archive_fields


class DepotResultCenterDialogA16_20(DepotResultCenterDialogA16_19):
    """a16.20: move archive dashboard to header and clarify period summary."""

    def __init__(self, master, **kwargs) -> None:
        self._a1620_top_dashboard = None
        super().__init__(master, **kwargs)
        self._install_top_dashboard()
        if getattr(self, "_archive_parts", None):
            self._show_archive_part(getattr(self, "_archive_index", 0))

    def _install_top_dashboard(self) -> None:
        detail = getattr(self, "_detail", None)
        search_entry = getattr(self, "_archive_search_entry", None)
        navigation = getattr(self, "_archive_navigation", None)
        old_dashboard = getattr(self, "_a11_dashboard", None)
        if detail is None or search_entry is None or navigation is None:
            return
        tab = detail.master

        # Header is row 0. Insert the dashboard directly below it, then search/body.
        search = search_entry.master
        search.grid_configure(row=2, pady=(2, 6))
        navigation.grid_configure(row=3)
        detail.grid_configure(row=3)
        tab.grid_rowconfigure(3, weight=1)
        tab.grid_rowconfigure(2, weight=0)
        if old_dashboard is not None:
            try:
                old_dashboard.grid_remove()
            except Exception:
                pass

        panel = ctk.CTkFrame(tab)
        panel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(2, 5))
        panel.grid_columnconfigure(0, weight=1)
        for col in range(1, 5):
            panel.grid_columnconfigure(col, weight=1)
        self._a1620_top_dashboard = panel

        real_rows = [r for r in getattr(self, "_archive_parts", []) if not r.get("is_all_archive_parts")]
        complete = sum(1 for r in real_rows if not _missing_archive_fields(r))
        missing = len(real_rows) - complete
        deviations = self.model.get("review_points") or self.model.get("deviations") or []
        review_count = len(deviations) if isinstance(deviations, list) else 0

        specs = (
            ("Datagrunnlag", f"Komplett {complete}\nMangler {missing}"),
            ("Arkivdeler", str(len(real_rows))),
            ("Komplett data", str(complete)),
            ("Mangler data", str(missing)),
            ("Vurderingspunkter", str(review_count)),
        )
        for col, (label, value) in enumerate(specs):
            card = ctk.CTkFrame(panel, fg_color="transparent")
            card.grid(row=0, column=col, sticky="nsew", padx=7, pady=5)
            ctk.CTkLabel(card, text=value, anchor="w",
                         font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(
                row=0, column=0, sticky="w", padx=5, pady=(1, 0))
            ctk.CTkLabel(card, text=label, anchor="w", text_color=theme.TEXT_MUTED,
                         font=theme.font(theme.SMALL_SIZE)).grid(
                row=1, column=0, sticky="w", padx=5, pady=(0, 1))

        # The old status line duplicates the new dashboard. Keep only the heading.
        try:
            header = next(w for w in tab.winfo_children() if int(w.grid_info().get("row", -1)) == 0)
            for child in header.winfo_children():
                info = child.grid_info()
                if int(info.get("row", -1)) == 1:
                    child.grid_remove()
        except Exception:
            pass

        # With the old dashboard gone, pull title/subtitle/tabs to the top of detail.
        title = getattr(self, "_archive_title", None)
        subtitle = getattr(self, "_archive_subtitle", None)
        tabs = getattr(self, "_a10_tabs", None)
        if title is not None:
            title.grid_configure(row=0, pady=(7, 1))
        if subtitle is not None:
            subtitle.grid_configure(row=1, pady=(0, 5))
        if tabs is not None:
            tabs.grid_configure(row=2, rowspan=3, pady=(0, 6))

    @staticmethod
    def _range_for(values: dict[int, int]) -> str:
        years = [int(y) for y, n in values.items() if int(n or 0) > 0]
        if not years:
            return "–"
        return str(min(years)) if min(years) == max(years) else f"{min(years)}–{max(years)}"

    def _refresh_period_columns(self, index: int) -> None:
        label = getattr(self, "_a164_period_text", None)
        if label is None or not getattr(self, "_archive_parts", None):
            return
        row = self._archive_parts[index]
        mappe = self._range_for(self._series(row, "folder"))
        reg = self._range_for(self._series(row, "journal"))
        dokument = self._range_for(self._series(row, "document_description"))
        start, end, source = self._effective_period(row, index)
        reviewed = self._period_text((start, end))
        label.configure(
            text=(
                f"Mappe/sak: {mappe}     |     Registrering/JP: {reg}     |     Dokument: {dokument}\n"
                f"Vurdert ytterår: {reviewed} ({source})"
            )
        )

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._refresh_period_columns(index)
