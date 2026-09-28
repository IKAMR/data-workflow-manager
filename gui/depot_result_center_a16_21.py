from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_19 import DepotResultCenterDialogA16_19
from .depot_result_views_a29 import _missing_archive_fields


class DepotResultCenterDialogA16_21(DepotResultCenterDialogA16_19):
    """a16.21: safe archive summary compaction without re-gridding the result body."""

    def __init__(self, master, **kwargs) -> None:
        self._a1621_header_dashboard = None
        self._a1621_period_frame = None
        self._a1621_period_labels = []
        self._a1621_period_review = None
        super().__init__(master, **kwargs)
        self._install_header_dashboard()
        self._install_period_columns()
        if getattr(self, "_archive_parts", None):
            self._show_archive_part(getattr(self, "_archive_index", 0))

    def _install_header_dashboard(self) -> None:
        """Move the data-status cards into the existing archive header only.

        Important: unlike a16.20 this does NOT move the search frame, navigation,
        or detail frame. The old dashboard row is simply removed so the existing
        body can collapse upward naturally.
        """
        detail = getattr(self, "_detail", None)
        old_dashboard = getattr(self, "_a11_dashboard", None)
        if detail is None:
            return
        tab = detail.master

        # Find the existing header row. Its second row is the old compact status line.
        header = None
        for child in tab.winfo_children():
            try:
                if int(child.grid_info().get("row", -1)) == 0:
                    header = child
                    break
            except Exception:
                continue
        if header is None:
            return

        # Hide only the duplicated old status line inside the header.
        for child in header.winfo_children():
            try:
                if int(child.grid_info().get("row", -1)) == 1:
                    child.grid_remove()
            except Exception:
                pass

        panel = ctk.CTkFrame(header, fg_color="transparent")
        panel.grid(row=1, column=0, columnspan=8, sticky="ew", padx=(4, 4), pady=(1, 4))
        for col in range(5):
            panel.grid_columnconfigure(col, weight=1, uniform="a1621status")
        self._a1621_header_dashboard = panel

        real_rows = [r for r in getattr(self, "_archive_parts", []) if not r.get("is_all_archive_parts")]
        complete = sum(1 for r in real_rows if not _missing_archive_fields(r))
        missing = max(0, len(real_rows) - complete)
        deviations = self.model.get("review_points") or self.model.get("deviations") or []
        review_count = len(deviations) if isinstance(deviations, list) else 0

        specs = (
            ("Datagrunnlag", f"Komplett {complete}   Mangler {missing}"),
            ("Arkivdeler", str(len(real_rows))),
            ("Komplett data", str(complete)),
            ("Mangler data", str(missing)),
            ("Vurderingspunkter", str(review_count)),
        )
        for col, (label, value) in enumerate(specs):
            card = ctk.CTkFrame(panel, fg_color="transparent")
            card.grid(row=0, column=col, sticky="ew", padx=7, pady=(0, 1))
            ctk.CTkLabel(
                card, text=value, anchor="w",
                font=theme.font(theme.NORMAL_SIZE, weight="bold"),
            ).grid(row=0, column=0, sticky="w", padx=2, pady=(0, 0))
            ctk.CTkLabel(
                card, text=label, anchor="w", text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, sticky="w", padx=2, pady=(0, 0))

        # Remove the old body dashboard. Do not touch the body's row assignments.
        if old_dashboard is not None:
            try:
                old_dashboard.grid_remove()
            except Exception:
                pass

    @staticmethod
    def _range_for(values: dict[int, int]) -> str:
        years = [int(y) for y, n in values.items() if int(n or 0) > 0]
        if not years:
            return "–"
        lo, hi = min(years), max(years)
        return str(lo) if lo == hi else f"{lo}–{hi}"

    def _install_period_columns(self) -> None:
        """Replace the old period text line with three aligned visual columns."""
        old = getattr(self, "_a164_period_text", None)
        if old is None:
            return
        try:
            parent = old.master
            info = dict(old.grid_info())
            old.grid_remove()
        except Exception:
            return

        frame = ctk.CTkFrame(parent, fg_color="transparent")
        grid_args = {
            k: v for k, v in info.items()
            if k in {"row", "column", "rowspan", "columnspan", "sticky", "padx", "pady", "ipadx", "ipady"}
        }
        frame.grid(**grid_args)
        for col in range(3):
            frame.grid_columnconfigure(col, weight=1, uniform="a1621period")
        self._a1621_period_frame = frame

        self._a1621_period_labels = []
        for col, heading in enumerate(("Mappe/sak", "Registrering/JP", "Dokument")):
            cell = ctk.CTkFrame(frame, fg_color="transparent")
            cell.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 8), pady=(0, 1))
            ctk.CTkLabel(
                cell, text=heading, anchor="w",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=0, column=0, sticky="w")
            value = ctk.CTkLabel(
                cell, text="–", anchor="w", text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            )
            value.grid(row=1, column=0, sticky="w")
            self._a1621_period_labels.append(value)

        review = ctk.CTkLabel(
            frame, text="", anchor="w", text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        )
        review.grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 0))
        self._a1621_period_review = review

    def _refresh_period_columns(self, index: int) -> None:
        if len(self._a1621_period_labels) != 3 or not getattr(self, "_archive_parts", None):
            return
        row = self._archive_parts[index]
        values = (
            self._range_for(self._series(row, "folder")),
            self._range_for(self._series(row, "journal")),
            self._range_for(self._series(row, "document_description")),
        )
        for widget, value in zip(self._a1621_period_labels, values):
            widget.configure(text=value)

        start, end, source = self._effective_period(row, index)
        reviewed = self._period_text((start, end))
        if self._a1621_period_review is not None:
            self._a1621_period_review.configure(text=f"Vurdert ytterår: {reviewed} ({source})")

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._refresh_period_columns(index)
