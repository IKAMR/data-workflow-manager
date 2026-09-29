from __future__ import annotations

from . import theme
from .depot_result_center_a21_7 import DepotResultCenterDialogA21_7
from .depot_result_views_a22 import _identity
from .depot_result_views_a29 import _missing_archive_fields


class DepotResultCenterDialogA21_8(DepotResultCenterDialogA21_7):
    """a21.8: keep the approved archive queue, but left-align multiline identity data.

    Presentation only; no new Noark analysis is performed.
    """

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._a217_refresh_archive_queue()
        self._a218_left_align_archive_queue()


    def _a218_left_align_archive_queue(self) -> None:
        """Make title, systemID/UUID and status share the same left edge."""
        for button in list(getattr(self, "_archive_buttons", []) or []):
            try:
                button.configure(anchor="w", justify="left")
            except Exception:
                pass

    @staticmethod
    def _a217_compact_title(value: object, max_chars: int = 42) -> str:
        text = " ".join(str(value or "Uten tittel").split())
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1].rstrip() + "…"

    def _a217_refresh_archive_queue(self) -> None:
        parts = list(getattr(self, "_archive_parts", []) or [])
        buttons = list(getattr(self, "_archive_buttons", []) or [])
        if not parts or not buttons:
            return

        for index, button in enumerate(buttons):
            if index >= len(parts):
                break
            row = parts[index]
            system_id, title = _identity(row, index)
            missing = _missing_archive_fields(row)
            status = "Komplett data" if not missing else f"Mangler data: {len(missing)}"
            period = self._a217_observed_period(row)
            period_text = f" · obs. {period}" if period else ""
            button.configure(
                text=(
                    f"{self._a217_compact_title(title)}\n"
                    f"{system_id}\n"
                    f"{status}{period_text}"
                ),
                height=72,
                anchor="w",
                font=theme.font(theme.SMALL_SIZE),
            )

        self._a217_mark_selected_archive()
        self._a218_left_align_archive_queue()

    @staticmethod
    def _a217_observed_period(row: dict) -> str:
        # The materialized rows have used a few names through the a-series.
        # Read only existing values; do not derive a new period here.
        pairs = (
            ("observed_start", "observed_end"),
            ("observed_start_year", "observed_end_year"),
            ("period_start", "period_end"),
        )
        for start_key, end_key in pairs:
            start, end = row.get(start_key), row.get(end_key)
            if start is not None or end is not None:
                return f"{start if start is not None else '–'}–{end if end is not None else '–'}"
        return ""

    def _a217_mark_selected_archive(self) -> None:
        selected = int(getattr(self, "_archive_index", 0) or 0)
        for index, button in enumerate(getattr(self, "_archive_buttons", []) or []):
            try:
                if index == selected:
                    button.configure(fg_color=theme.BLUE)
                else:
                    button.configure(fg_color=theme.BUTTON_BG)
            except Exception:
                pass

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if hasattr(self, "_archive_buttons"):
            self._a217_mark_selected_archive()
            self._a218_left_align_archive_queue()
