"""a18: choose newest run when a new history entry replaces the old newest.

Keep intentional selections of older runs intact. This applies to both the
advanced run-history pane and the separate Kjoeredetaljer window.
"""
from __future__ import annotations



def _row_key(tree, index=0):
    if tree is None or tree.topLevelItemCount() <= index:
        return None
    from PySide6.QtCore import Qt
    item = tree.topLevelItem(index)
    return str(item.data(0, Qt.ItemDataRole.UserRole)) if item is not None else None


def install_active_run_log(window) -> None:
    """Install per-app selection policy without replacing legacy GUI classes."""
    # GUI startup tests use lightweight fake Qt modules. Avoid loading real
    # Qt widgets until the actual history-capable main window is available.
    if not hasattr(window, "_a11_refresh_operation_history") or not hasattr(window, "_a11_open_history_log"):
        return
    from gui_qt.detached_log_window_v018_a9 import DetachedRunWindow
    if not getattr(DetachedRunWindow, '_a18_log_selection_installed', False):
        original_set_history = DetachedRunWindow.set_history

        def set_history(self, rows, selected=None):
            previous_head = _row_key(self.history_tree)
            current = self._selected_history_key()
            newest = (str(rows[0][5]) + '|' + str(rows[0][6])) if rows else None
            if newest and previous_head and current == previous_head and newest != previous_head:
                # Existing selection merely tracked the old newest item.
                self.history_tree.setCurrentItem(None)
                selected = newest
            return original_set_history(self, rows, selected=selected)

        DetachedRunWindow.set_history = set_history
        DetachedRunWindow._a18_log_selection_installed = True

    if getattr(window, '_a18_log_selection_installed', False):
        return
    if not hasattr(window, '_a11_refresh_operation_history'):
        return
    original_refresh = window._a11_refresh_operation_history
    original_history_log = window._a11_open_history_log

    def open_history_log(key):
        # Kjoeredetaljer is often opened while a workflow is actively running.
        # The history table only contains finished operations at that point;
        # following its old selected row would reopen yesterday's log.
        running = (getattr(window, '_worker', None) is not None
                   or bool(getattr(window.api, 'running', False)))
        if running:
            window._a8_show_job_log()
            combo = getattr(window, 'job_run_combo', None)
            if combo is not None and combo.count():
                # run_log_history is most-recent-first. Ignore legacy snapshots.
                combo.setCurrentIndex(0)
                window._a8_show_selected_run()
                window._a9_sync_detached_log_choices()
            return
        return original_history_log(key)

    window._a11_open_history_log = open_history_log

    def refresh_operation_history():
        tree = getattr(window, 'run_history_tree', None)
        previous_head = _row_key(tree)
        previous_selected = window._a11_selected_history_key() if tree is not None else None
        result = original_refresh()
        if tree is not None and previous_head and previous_selected == previous_head:
            new_head = _row_key(tree)
            if new_head and new_head != previous_head:
                tree.setCurrentItem(tree.topLevelItem(0))
                if hasattr(window, '_a9_sync_detached_run'):
                    window._a9_sync_detached_run()
        return result

    window._a11_refresh_operation_history = refresh_operation_history
    window._a18_log_selection_installed = True
