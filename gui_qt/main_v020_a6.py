"""v0.2.1-a1: retain a6 result navigation and add read-only XPath explorer."""
from __future__ import annotations

from gui_qt.basic_main_v0113_a2 import DwmMainWindow as _ExistingMainWindow


class DwmMainWindow(_ExistingMainWindow):
    def _a12_open_result_center(self, *args, **kwargs):
        existing = tuple(getattr(self, '_a12_result_windows', ()))
        outcome = super()._a12_open_result_center(*args, **kwargs)
        from gui_qt.result_navigation_v020_a6 import install_compact_result_navigation
        from gui_qt.noark5_xpath_audit_v021_a1 import install_xpath_catalog_link
        for viewer in getattr(self, '_a12_result_windows', ()):
            if viewer not in existing:
                install_compact_result_navigation(viewer)
                install_xpath_catalog_link(viewer)
        return outcome
