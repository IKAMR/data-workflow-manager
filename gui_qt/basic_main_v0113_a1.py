"""v0.1.13-a1: explicit results-view routing, preserving the stable Basic window.

Only the result-center class changes. No monkeypatches of Qt class objects.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from app.format_assessment_v0111_a2 import chosen_format_source
from .appearance_v0110_a3 import stylesheet_for
from .basic_main_v0111_a1 import DwmMainWindow as _StableBasicWindow
from .result_center_v0113_a1 import ResultCenterWindow


class DwmMainWindow(_StableBasicWindow):
    def _a12_open_result_center(self, _checked=False, *, depot=False):
        if not self._active_id:
            QMessageBox.information(self, 'Resultatvisninger', 'Velg en jobb i jobblisten.')
            return
        try:
            job = self.api.job_details(self._active_id).job
        except Exception as exc:
            QMessageBox.warning(self, 'Resultatvisninger', str(exc))
            return
        dialog = ResultCenterWindow(
            job.effective_work_operations,
            display_name=job.job_id + ' - ' + job.name,
            available_jobs=self.api.report_candidates(),
            report_api=self.api,
            on_generate_report=self._a12_open_selected_report,
            format_assessment_source=chosen_format_source(self.api.settings),
        )
        try:
            ids = {item.operation_id for item in self.api.job_details(self._active_id).operations}
            if 'run_noark5_xpath_tests_2026' not in ids:
                if 'siegfried_pronom_identification' in ids:
                    dialog.tabs.setCurrentWidget(dialog._sf_page)
                elif 'arkade5_pronom_analysis' in ids:
                    dialog.tabs.setCurrentWidget(dialog._pages['PRONOM'])
                elif 'arkade5_noark5_test' in ids:
                    dialog.tabs.setCurrentWidget(dialog._pages['Arkade 5'])
        except (RuntimeError, AttributeError, ValueError):
            pass
        if depot:
            dialog.show_depot_review()
        dialog.setStyleSheet(stylesheet_for(self.api.settings))
        dialog.setFont(self.font())
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._a12_result_windows.append(dialog)
        dialog.destroyed.connect(
            lambda _obj=None, win=dialog: (
                self._a12_result_windows.remove(win)
                if win in self._a12_result_windows else None
            )
        )
        dialog.show()
        self._a3_place_dialog(dialog, 'results')
