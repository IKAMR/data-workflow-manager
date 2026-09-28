from __future__ import annotations

from .depot_result_center_a16_26 import DepotResultCenterDialogA16_26


class DepotResultCenterDialogA16_28(DepotResultCenterDialogA16_26):
    """a16.28: keep archive-part summary pair cards scoped to the selected row."""

    def _render_a10_archive_part(self, index: int) -> None:
        # Let a16.26 render the complete summary/control surface first.
        super()._render_a10_archive_part(index)

        # a16.24 already knows how to resolve the real case count per archive
        # part from the materialized c13 data.  Later layers did not call that
        # refresh after changing archive part, leaving the three pair cards on
        # the totals from "Alle arkivdeler".  Refresh only those cards here.
        self._refresh_pair_kpis(index)
