"""v0.2.1-a13: retain all a6 result navigation, add a13 human review entry."""
from __future__ import annotations

from gui_qt.basic_main_v0113_a2 import DwmMainWindow as _ExistingMainWindow


class DwmMainWindow(_ExistingMainWindow):
    def _a12_open_result_center(self, *args, **kwargs):
        existing = tuple(getattr(self, '_a12_result_windows', ()))
        outcome = super()._a12_open_result_center(*args, **kwargs)
        from gui_qt.result_navigation_v020_a6 import install_compact_result_navigation
        from gui_qt.noark5_xpath_audit_v021_a1 import install_xpath_catalog_link
        from gui_qt.qa_review_v021_a13 import install_qa_review_panel
        for viewer in getattr(self, '_a12_result_windows', ()):
            if viewer not in existing:
                install_compact_result_navigation(viewer)
                install_xpath_catalog_link(viewer)
                install_qa_review_panel(viewer)
        return outcome
