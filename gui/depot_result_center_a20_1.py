from __future__ import annotations

from . import theme
from .depot_result_center_a19_5 import DepotResultCenterDialogA19_5


class DepotResultCenterDialogA20_1(DepotResultCenterDialogA19_5):
    """a20.1: detail-first archive-part layout with semantic period-profile colours."""

    _A201_SERIES_COLORS = (
        theme.BLUE,
        theme.CATEGORY_COLORS["Innhold"],
        theme.CATEGORY_COLORS["Metadata"],
    )

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._a201_place_period_profile_last()

    def _a201_place_period_profile_last(self) -> None:
        """Keep facts as the primary scroll surface and period profiles at the bottom.

        This is deliberately a presentation-only re-grid.  The inherited widgets,
        review logic and materialized data remain unchanged.
        """
        period = getattr(self, "_a1621_period_frame", None)
        fact = getattr(self, "_a195_fact_panel", None)
        if period is None or fact is None:
            return
        try:
            if period.master is not fact.master:
                return
            siblings = [
                child for child in period.master.winfo_children()
                if child is not period and child.grid_info()
            ]
            last_row = max(
                [int(child.grid_info().get("row", 0)) for child in siblings] + [0]
            )
            period.grid_configure(row=last_row + 1, pady=(8, 12), sticky="ew")
        except Exception:
            # Layout refinement must never prevent the result view from opening.
            return

    def _a194_draw_period_profile(self, index: int) -> None:
        """Draw inherited profile, then recolour the activity bars by content domain."""
        super()._a194_draw_period_profile(index)
        if not (0 <= index < len(getattr(self, "_a194_period_canvases", []))):
            return
        canvas = self._a194_period_canvases[index]
        payload = self._a194_period_payloads[index] or {}
        main_start = payload.get("main_start")
        main_end = payload.get("main_end")
        if main_start is None or main_end is None:
            return

        # Repaint only activity rectangles. Blue assessment markers and muted
        # outliers retain their inherited semantic colours.
        color = self._A201_SERIES_COLORS[index]
        try:
            for item in canvas.find_all():
                if canvas.type(item) != "rectangle":
                    continue
                fill = canvas.itemcget(item, "fill")
                if fill == theme.TEXT_SUB:
                    canvas.itemconfigure(item, fill=color)
        except Exception:
            return

    def _a195_render_fact_profile(self, index: int) -> None:
        super()._a195_render_fact_profile(index)
        self._a201_place_period_profile_last()

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._a201_place_period_profile_last()
