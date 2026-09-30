from __future__ import annotations

from . import theme
from .depot_result_center_a21_17 import DepotResultCenterDialogA21_17
from .depot_result_views_a29 import _missing_archive_fields


class DepotResultCenterDialogA22_1(DepotResultCenterDialogA21_17):
    """a22.1: make archive-part readiness explicit for real depot review.

    This first a22 step deliberately reuses the canonical materialized analysis.
    It adds no new analysis and changes no source facts; it only turns existing
    completeness/period evidence into a clearer review cue in Arkivdeler.
    """

    @staticmethod
    def _a221_review_state(row: dict, period: str) -> tuple[str, str]:
        missing = list(_missing_archive_fields(row) or [])
        if missing:
            return (
                "Krever gjennomgang",
                f"{len(missing)} manglende nøkkelfelt i datagrunnlaget",
            )
        if not period:
            return (
                "Krever gjennomgang",
                "observert periode mangler",
            )
        return (
            "Klar for faglig vurdering",
            "datagrunnlag komplett",
        )

    def _a221_refresh_archive_header(self, index: int) -> None:
        parts = list(getattr(self, "_archive_parts", []) or [])
        if not (0 <= int(index) < len(parts)):
            return

        row = parts[int(index)]
        title_widget = getattr(self, "_archive_title", None)
        subtitle_widget = getattr(self, "_archive_subtitle", None)
        if title_widget is None or subtitle_widget is None:
            return

        period = self._a2111_observed_period(row)
        state, reason = self._a221_review_state(row, period)
        real_count = self._a219_real_archive_count(parts)
        period_text = period or "ikke utledet"

        try:
            if row.get("is_all_archive_parts"):
                title_widget.configure(
                    text="Alle arkivdeler – samlet vurderingsgrunnlag",
                    anchor="w",
                    font=theme.font(theme.TITLE_SIZE, weight="bold"),
                )
                subtitle_widget.configure(
                    text=(
                        f"{real_count} arkivdeler   |   Observert periode: {period_text}   |   "
                        f"Vurderingsgrunnlag: {state} – {reason}"
                    ),
                    anchor="w",
                    justify="left",
                )
                return

            system_id, title = self._a2110_identity(row, int(index))
            visible_number = 1 + sum(
                1 for previous in parts[: int(index)]
                if not previous.get("is_all_archive_parts")
            )
            title_widget.configure(
                text=f"Arkivdel: {title}",
                anchor="w",
                font=theme.font(theme.TITLE_SIZE, weight="bold"),
            )
            subtitle_widget.configure(
                text=(
                    f"systemID: {system_id}   |   Arkivdel {visible_number} av {real_count}   |   "
                    f"Observert: {period_text}   |   Vurderingsgrunnlag: {state} – {reason}"
                ),
                anchor="w",
                justify="left",
            )
        except Exception:
            return

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._a221_refresh_archive_header(getattr(self, "_archive_index", 0))

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._a221_refresh_archive_header(index)
