from __future__ import annotations

from . import depot_result_views_a26 as _a26_window_layer
from .depot_result_center_a14_2 import DepotResultCenterDialogA14_2
from .window_placement import present_child_over_parent, release_parent_work_window


class DepotResultCenterDialogA14_3(DepotResultCenterDialogA14_2):
    """v0.1.6-a14.3.1: stable first page and one controlled foreground presentation."""

    def __init__(self, master, **kwargs) -> None:
        # The inherited a6 layer presents the same window while the long a31 ->
        # a14.2 constructor chain is still rebuilding tabs.  That creates several
        # competing Windows focus/Z-order callbacks and is the source of the
        # visible blinking.  Suppress only those inherited presentation calls
        # during this constructor; geometry/layout logic is left untouched.
        original_release = _a26_window_layer.release_parent_work_window
        original_native = _a26_window_layer.present_native_work_window
        original_child = _a26_window_layer.present_child_over_parent
        try:
            _a26_window_layer.release_parent_work_window = lambda *_a, **_k: None
            _a26_window_layer.present_native_work_window = lambda *_a, **_k: None
            _a26_window_layer.present_child_over_parent = lambda *_a, **_k: None
            super().__init__(master, **kwargs)
        finally:
            _a26_window_layer.release_parent_work_window = original_release
            _a26_window_layer.present_native_work_window = original_native
            _a26_window_layer.present_child_over_parent = original_child

        # Present the completed result centre once, after all inherited tab and
        # layout construction has finished.  The helper performs the Windows
        # front placement and then returns the window to normal non-topmost use.
        release_parent_work_window(master)
        present_child_over_parent(self, master)

    def _activate_archive_parts_tab(self) -> None:
        """Override the historical a2 default-tab callback.

        a2 schedules this method with after_idle while a14.2 later rebuilds the
        top-level navigation.  Selecting Arkivdeler from that old callback could
        leave the tab highlighted before its content had been mapped.  The result
        centre now opens on Oversikt; Arkivdeler is rendered normally when chosen.
        """
        tabs = self._root_tabview()
        if tabs is None:
            return
        try:
            tabs.set("Oversikt")
            self.update_idletasks()
        except Exception:
            pass
