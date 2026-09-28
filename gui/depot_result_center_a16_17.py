from __future__ import annotations

from .depot_result_center_a16_15 import DepotResultCenterDialogA16_15
from .depot_result_center_a16_16 import DepotResultCenterDialogA16_16


class DepotResultCenterDialogA16_17(DepotResultCenterDialogA16_16):
    """a16.17: guard reviewed-period widgets during inherited UI construction."""

    def _show_archive_part(self, index: int) -> None:
        # Older layers call this virtual method while their constructors are still
        # building the dialog.  a16.16's StringVars do not exist yet at that point.
        if getattr(self, "_a1616_start_var", None) is None or getattr(
            self, "_a1616_end_var", None
        ) is None:
            DepotResultCenterDialogA16_15._show_archive_part(self, index)
            return
        DepotResultCenterDialogA16_16._show_archive_part(self, index)
