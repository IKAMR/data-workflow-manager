from __future__ import annotations

from .depot_result_views_a25 import DepotResultViewsDialogA25
from .window_geometry import apply_result_review_opening_mode
from .window_placement import (
    present_child_over_parent,
    present_native_work_window,
    release_parent_work_window,
)


class DepotResultViewsDialogA26(DepotResultViewsDialogA25):
    """v0.1.6-a6: screen-aware opening mode for the result-review window."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # a4/a5 have now completed all native-window, default-tab and
        # archive-part layout work. Release the calling work window from
        # Windows Z-order/topmost state before presenting this child.
        release_parent_work_window(master)
        apply_result_review_opening_mode(self, wide_ratio=2.0)
        present_native_work_window(self)
        present_child_over_parent(self, master)
