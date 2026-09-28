from __future__ import annotations

from .depot_result_center_a16_29 import DepotResultCenterDialogA16_29


class DepotResultCenterDialogA16_30(DepotResultCenterDialogA16_29):
    """a16.30: summary pair cards always follow the row actually rendered."""

    def _render_a10_archive_part(self, index: int) -> None:
        # This method is the reliable render point for Sammendrag.  Refresh the
        # three header cards here, after the inherited content has rendered.
        super()._render_a10_archive_part(index)
        self._a1630_refresh_pair_cards(index)

    def _a1630_refresh_pair_cards(self, index: int) -> None:
        parts = getattr(self, "_archive_parts", None) or []
        values = getattr(self, "_a1618_pair_values", None) or {}
        if not (0 <= index < len(parts)) or not values:
            return

        row = parts[index]
        for (left, right), label in values.items():
            left_value = row.get(left)
            if left == "folder_count" and right == "case_folder_count":
                right_value = self._case_count_for_row(row)
            else:
                right_value = row.get(right)
            try:
                label.configure(
                    text=f"{self._fmt_count(left_value)} / {self._fmt_count(right_value)}"
                )
            except Exception:
                pass
