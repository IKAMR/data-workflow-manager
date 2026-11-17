"""DWM v0.2.2-a3: keep the stable a2 shell; expose existing KS/depot flow.

The internal VERSION stays at 0.2.2-a1 (deliberate test-regime choice).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QPushButton

from gui_qt.basic_main_v0113_a2 import DwmMainWindow as _ExistingMainWindow


class DwmMainWindow(_ExistingMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._a3_install_qa_shortcuts()

    def _a3_install_qa_shortcuts(self):
        """No new top-level windows at startup and no Qt event filters."""
        self.a3_qa_action = QAction("Avvik, kvalitetssikring og godkjenning…", self)
        self.a3_qa_action.setToolTip(
            "Dokumenter kildefunn; lag kvalitetssikrings- og godkjenningsrapporter som utkast")
        self.a3_qa_action.triggered.connect(self._a3_open_qa)
        # Visible only when the existing Advanced menu bar is visible.
        menu = next((action.menu() for action in self.menuBar().actions()
                     if action.menu() is not None
                     and action.text().replace("&", "").strip() == "Rapport"), None)
        if menu is not None:
            menu.insertAction(self.report_selected_action, self.a3_qa_action)
        # Simple mode hides the native menu. Put the same action in its own
        # existing Overview, not in a second hidden workflow/joblist.
        overview = getattr(self, "_a2_overview_page", None)
        start = getattr(self, "_a2_overview_start", None)
        if overview is not None and start is not None and overview.layout() is not None:
            self.a3_basic_qa_button = QPushButton("Avvik / KS / godkjenning…", overview)
            self.a3_basic_qa_button.setToolTip(
                "Tilgjengelig for ferdig kontrollerte jobber med en lagret depotrapport")
            self.a3_basic_qa_button.clicked.connect(self._a3_open_qa)
            layout = overview.layout()
            index = layout.indexOf(start)
            layout.insertWidget(index if index >= 0 else layout.count(),
                                self.a3_basic_qa_button, 0, Qt.AlignmentFlag.AlignRight)

    def _a3_open_qa(self, *_args):
        from gui_qt.qa_workflow_v022_a3 import open_active_job_qa
        open_active_job_qa(self)

    def _a12_open_result_center(self, *args, **kwargs):
        existing = tuple(getattr(self, "_a12_result_windows", ()))
        outcome = super()._a12_open_result_center(*args, **kwargs)
        from gui_qt.result_navigation_v020_a6 import install_compact_result_navigation
        from gui_qt.noark5_xpath_audit_v021_a1 import install_xpath_catalog_link
        from gui_qt.qa_workflow_v022_a3 import install_qa_review_panel
        from gui_qt.checklist_v021_a15 import install_depot_checklist
        for viewer in getattr(self, "_a12_result_windows", ()):
            if viewer not in existing:
                install_compact_result_navigation(viewer)
                install_xpath_catalog_link(viewer)
                install_qa_review_panel(viewer)
                install_depot_checklist(viewer)
        return outcome
