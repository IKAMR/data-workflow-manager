"""a6 GUI entry subclass: extend only the result window creation seam.

The established main window retains all Work controllers, result dialogs,
window persistence, dock modes and callbacks unchanged.
"""
from __future__ import annotations

from gui_qt.basic_main_v0113_a2 import DwmMainWindow as _ExistingMainWindow


class DwmMainWindow(_ExistingMainWindow):
    def _a12_open_result_center(self, *args, **kwargs):
        existing = tuple(getattr(self, '_a12_result_windows', ()))
        outcome = super()._a12_open_result_center(*args, **kwargs)
        from gui_qt.result_navigation_v020_a6 import install_compact_result_navigation
        for viewer in getattr(self, '_a12_result_windows', ()):
            if viewer not in existing:
                install_compact_result_navigation(viewer)
        return outcome
