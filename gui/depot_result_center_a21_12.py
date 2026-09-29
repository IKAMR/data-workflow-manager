from __future__ import annotations

from . import theme
from .depot_result_center_a21_11 import DepotResultCenterDialogA21_11
from .depot_result_views_a29 import _missing_archive_fields


class DepotResultCenterDialogA21_12(DepotResultCenterDialogA21_11):
    """a21.12: restore the compact, calm archive-part queue layout.

    Keep the visual rhythm from the earlier a21.7 queue, but remove UUID/systemID.
    Each card is deliberately limited to three centred lines:
      1. archive-part name (shortened only when necessary)
      2. observed period in parentheses
      3. completeness status
    """

    @staticmethod
    def _a2112_title(value: object, limit: int = 34) -> str:
        text = " ".join(str(value or "Uten tittel").split())
        if len(text) <= limit:
            return text

        # Keep whole words where possible. The queue is an orientation surface;
        # the full title remains available in the detail header.
        words = text.split()
        kept: list[str] = []
        used = 0
        for word in words:
            extra = len(word) + (1 if kept else 0)
            if used + extra > limit - 1:
                break
            kept.append(word)
            used += extra
        if kept:
            return " ".join(kept).rstrip(" ,;:-") + "…"
        return text[: limit - 1].rstrip() + "…"

    def _a2112_refresh_archive_queue(self) -> None:
        parts = list(getattr(self, "_archive_parts", []) or [])
        buttons = list(getattr(self, "_archive_buttons", []) or [])
        if not parts or not buttons:
            return

        for index, button in enumerate(buttons):
            if index >= len(parts):
                break

            row = parts[index]
            missing = _missing_archive_fields(row)
            status = "Komplett data" if not missing else f"Mangler data: {len(missing)}"
            period = self._a2111_observed_period(row)
            period_line = f"({period})" if period else ""

            if row.get("is_all_archive_parts"):
                title = "Alle arkivdeler"
            else:
                _system_id, raw_title = self._a2110_identity(row, index)
                title = self._a2112_title(raw_title)

            lines = [title]
            if period_line:
                lines.append(period_line)
            lines.append(status)

            try:
                button.configure(
                    text="\n".join(lines),
                    height=72,
                    anchor="center",
                    font=theme.font(theme.SMALL_SIZE),
                )
            except Exception:
                continue

        self._a217_mark_selected_archive()

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._a2112_refresh_archive_queue()

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._a2112_refresh_archive_queue()
