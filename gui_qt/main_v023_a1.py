"""v0.2.3-a1: use the source-linked inspector from both Basic and Advanced KS.

Preserve all a12 actions, job runner, Work model, and startup safety.  This
module is never imported by normal unit-test-only code paths without Qt.
"""
from __future__ import annotations

from pathlib import Path

from gui_qt.main_v022_a12 import DwmMainWindow as _A12Window


class DwmMainWindow(_A12Window):
    def _a12_open_ks_workshop(self, _checked=False):
        from PySide6.QtWidgets import QMessageBox
        if (getattr(self, '_worker', None) is not None or self.api.running
                or getattr(self, '_job_controls_running', False)):
            QMessageBox.information(self, 'Kvalitetssikring',
                                    'Avslutt pågående jobb før du registrerer faglige vurderinger.')
            return
        job_id = self._active_id
        if not job_id:
            QMessageBox.information(self, 'Kvalitetssikring', 'Velg et uttrekk i jobblisten først.')
            return
        try:
            view = self.api.job_details(job_id).job
            work = getattr(view, 'effective_work_operations', None)
            if not work or not Path(work).is_dir():
                raise ValueError('Valgt jobb har ikke en tilgjengelig Work-mappe')
            from gui_qt.ks_inspector_v023_a1 import KsWorkshopDialog
            dialog = KsWorkshopDialog(work, self)
            dialog.exec()
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kvalitetssikring',
                                'KS-grunnlaget kunne ikke åpnes. Kontroller at jobbens A200–A260 '
                                'og depotrapport er ferdige.\n\n' + str(exc))
