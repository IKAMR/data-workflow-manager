from __future__ import annotations

from . import theme
from .depot_result_center_a21_10 import DepotResultCenterDialogA21_10
from .depot_result_views_a29 import _missing_archive_fields


class DepotResultCenterDialogA21_11(DepotResultCenterDialogA21_10):
    """a21.11: clean archive-part cards.

    Left queue contract:
      1. Archive-part name, shortened intelligently if necessary.
      2. Observed period when available.
      3. Data completeness status.

    UUID/systemID is deliberately omitted from the queue.
    """

    _SHORT_NAME_KEYS = (
        "short_name",
        "shortName",
        "kortnavn",
        "short_title",
        "archive_part_short_name",
        "archivePartShortName",
        "abbreviation",
    )

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._a2111_refresh_archive_queue()

    @staticmethod
    def _a2111_compact_title(value: object, limit: int = 38) -> str:
        text = " ".join(str(value or "Uten tittel").split())
        if len(text) <= limit:
            return text

        # Prefer keeping whole words. If the title still cannot fit,
        # preserve both beginning and ending so distinguishing suffixes survive.
        words = text.split()
        kept = []
        used = 0
        for word in words:
            extra = len(word) + (1 if kept else 0)
            if used + extra > limit - 1:
                break
            kept.append(word)
            used += extra
        if len(kept) >= 2:
            return " ".join(kept) + "…"

        head = max(12, (limit - 3) // 2)
        tail = max(8, limit - 3 - head)
        return text[:head].rstrip() + "…" + text[-tail:].lstrip()

    @classmethod
    def _a2111_materialized_short_name(cls, row: dict) -> str:
        # Identity metadata is materialized under archive_part in the depot report.
        # Search both the row and that identity object before falling back to UI text.
        identity = row.get("archive_part") or {}
        for source in (identity, row):
            if not isinstance(source, dict):
                continue
            for key in cls._SHORT_NAME_KEYS:
                value = source.get(key)
                if value not in (None, ""):
                    return " ".join(str(value).split())
        return ""

    def _a2111_observed_period(self, row: dict) -> str:
        # First retain any already-materialized period fields used by earlier layers.
        period = self._a217_observed_period(row)
        if period:
            return period

        # The visible period profiles already use these materialized year series.
        # Reuse the same data so the queue agrees with the graphs instead of
        # introducing another independent period interpretation.
        years: list[int] = []
        for kind in ("folder", "journal", "document_description"):
            try:
                series = self._series(row, kind) or {}
            except Exception:
                series = {}
            for year, count in series.items():
                try:
                    y = int(year)
                    n = int(count or 0)
                except (TypeError, ValueError):
                    continue
                if n > 0:
                    years.append(y)
        if years:
            return f"{min(years)}–{max(years)}"
        return ""

    @staticmethod
    def _a2111_presentational_short_name(title: str) -> str:
        """Return a compact UI label only when the full title is long.

        This is not persisted as Noark metadata. It only keeps the queue readable
        when no real short-name field is materialized.
        """
        text = " ".join(str(title or "").split())
        if len(text) <= 28:
            return ""
        # Prefer the first meaningful phrase and avoid cutting in the middle of a word.
        words = text.replace(",", " ").split()
        kept: list[str] = []
        used = 0
        for word in words:
            extra = len(word) + (1 if kept else 0)
            if used + extra > 24:
                break
            kept.append(word)
            used += extra
        return " ".join(kept).rstrip(" -–,") + ("…" if kept else "")

    def _a2111_refresh_archive_queue(self) -> None:
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
            period_text = f"({period})" if period else ""

            if row.get("is_all_archive_parts"):
                line1 = "Alle arkivdeler"
            else:
                _system_id, title = self._a2110_identity(row, index)
                line1 = self._a2111_compact_title(title, 34)

            # Keep the queue deliberately simple and visually stable:
            # name, observed period, completeness. UUID/systemID and any
            # materialized short-name stay in the detail view, not in the queue.
            text = f"{line1}\n{period_text}\n{status}" if period_text else f"{line1}\n{status}"
            try:
                button.configure(
                    text=text,
                    height=66,
                    anchor="w",
                    font=theme.font(theme.SMALL_SIZE),
                )
            except Exception:
                continue

        self._a217_mark_selected_archive()

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._a2111_refresh_archive_queue()
