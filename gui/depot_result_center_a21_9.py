from __future__ import annotations

from . import theme
from .depot_result_center_a21_7 import DepotResultCenterDialogA21_7
from .depot_result_views_a22 import _identity
from .depot_result_views_a29 import _missing_archive_fields


class DepotResultCenterDialogA21_9(DepotResultCenterDialogA21_7):
    """a21.9: clean archive queue identity and clearer archive-detail header.

    Presentation only. Existing materialized report data and review logic are reused.
    """

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._a219_refresh_archive_queue()
        self._a219_refresh_archive_header(getattr(self, "_archive_index", 0))

    @staticmethod
    def _a219_real_archive_count(parts) -> int:
        return sum(1 for row in (parts or []) if not row.get("is_all_archive_parts"))

    def _a219_refresh_archive_queue(self) -> None:
        # Keep the proven a21.7 queue styling/alignment, then clean the synthetic
        # "Alle arkivdeler" row so internal IDs never leak into the GUI.
        self._a217_refresh_archive_queue()
        parts = list(getattr(self, "_archive_parts", []) or [])
        buttons = list(getattr(self, "_archive_buttons", []) or [])
        if not parts or not buttons:
            return

        real_count = self._a219_real_archive_count(parts)
        for index, (row, button) in enumerate(zip(parts, buttons)):
            if not row.get("is_all_archive_parts"):
                continue
            missing = _missing_archive_fields(row)
            status = "Komplett data" if not missing else f"Mangler data: {len(missing)}"
            period = self._a217_observed_period(row)
            period_text = f" · obs. {period}" if period else ""
            try:
                button.configure(
                    text=(
                        "Alle arkivdeler\n"
                        f"{real_count} arkivdeler · samlet uttrekk\n"
                        f"{status}{period_text}"
                    ),
                    anchor="w",
                    height=72,
                )
            except Exception:
                pass
        self._a217_mark_selected_archive()

    def _a219_refresh_archive_header(self, index: int) -> None:
        parts = list(getattr(self, "_archive_parts", []) or [])
        if not (0 <= int(index) < len(parts)):
            return
        row = parts[int(index)]
        title_widget = getattr(self, "_archive_title", None)
        subtitle_widget = getattr(self, "_archive_subtitle", None)
        if title_widget is None or subtitle_widget is None:
            return

        missing = _missing_archive_fields(row)
        data_status = "Datagrunnlag: komplett" if not missing else f"Datagrunnlag: mangler {len(missing)}"
        period = self._a217_observed_period(row)
        period_text = f" · Observert: {period}" if period else ""
        real_count = self._a219_real_archive_count(parts)

        try:
            if row.get("is_all_archive_parts"):
                title_widget.configure(
                    text="Alle arkivdeler – samlet oversikt",
                    anchor="w",
                    font=theme.font(theme.TITLE_SIZE, weight="bold"),
                )
                subtitle_widget.configure(
                    text=f"{real_count} arkivdeler · {data_status}{period_text}",
                    anchor="w",
                )
                return

            system_id, title = _identity(row, int(index))
            visible_number = 1 + sum(
                1
                for previous in parts[: int(index)]
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
                    f"{data_status}{period_text}"
                ),
                anchor="w",
            )
        except Exception:
            # Presentation refinement must never block the result window.
            return

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._a219_refresh_archive_queue()
        self._a219_refresh_archive_header(index)
