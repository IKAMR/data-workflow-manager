from __future__ import annotations

from . import theme
from .depot_result_center_a21_9 import DepotResultCenterDialogA21_9
from .depot_result_views_a29 import _missing_archive_fields


class DepotResultCenterDialogA21_10(DepotResultCenterDialogA21_9):
    """a21.10: simplify archive-part cards in the left queue.

    Three lines only:
      1. Name
      2. Short name (YYYY-YYYY)
      3. Data completeness status

    UUID/systemID stays available in the detail header, not in the queue.
    """

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._a2110_refresh_archive_queue()

    @staticmethod
    def _a2110_short_name(row: dict, title: str) -> str:
        # Prefer a materialized short-name field when one exists.
        for key in (
            "short_name",
            "shortName",
            "kortnavn",
            "short_title",
            "archive_part_short_name",
            "archivePartShortName",
            "abbreviation",
        ):
            value = row.get(key)
            if value not in (None, ""):
                return " ".join(str(value).split())

        # Presentation fallback only; do not invent new Noark data.
        text = " ".join(str(title or "Uten tittel").split())
        if len(text) <= 30:
            return text
        return text[:29].rstrip() + "…"

    def _a2110_refresh_archive_queue(self) -> None:
        parts = list(getattr(self, "_archive_parts", []) or [])
        buttons = list(getattr(self, "_archive_buttons", []) or [])
        if not parts or not buttons:
            return

        real_count = self._a219_real_archive_count(parts)

        for index, button in enumerate(buttons):
            if index >= len(parts):
                break

            row = parts[index]
            missing = _missing_archive_fields(row)
            status = "Komplett data" if not missing else f"Mangler data: {len(missing)}"
            period = self._a217_observed_period(row)
            period_text = f" ({period})" if period else ""

            if row.get("is_all_archive_parts"):
                name = "Alle arkivdeler"
                short_name = f"{real_count} arkivdeler · samlet uttrekk"
            else:
                _system_id, name = self._a2110_identity(row, index)
                short_name = self._a2110_short_name(row, name)

            try:
                button.configure(
                    text=f"{name}\n{short_name}{period_text}\n{status}",
                    height=72,
                    anchor="w",
                    font=theme.font(theme.SMALL_SIZE),
                )
            except Exception:
                # Queue presentation must never block the result window.
                continue

        self._a217_mark_selected_archive()

    @staticmethod
    def _a2110_identity(row: dict, index: int):
        # Keep identity lookup inherited indirectly, but isolate the queue from UUID display.
        from .depot_result_views_a22 import _identity
        return _identity(row, index)

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._a2110_refresh_archive_queue()
