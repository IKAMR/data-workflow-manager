"""v0.2.3-a2: Noark metadata and standard-value inspection in Basic KS.

Keep the committed a1 workflow, job selection and safety guards unchanged.
Only the KS dialog implementation is extended.
"""
from __future__ import annotations

from pathlib import Path

from gui_qt.main_v023_a1 import DwmMainWindow as _A1Window


class DwmMainWindow(_A1Window):
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
            from gui_qt.ks_metadata_v023_a2 import KsWorkshopDialog
            dialog = KsWorkshopDialog(work, self)
            dialog.exec()
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kvalitetssikring',
                                'KS-grunnlaget kunne ikke åpnes. Kontroller at jobbens A200–A260 '
                                'og depotrapport er ferdige.\n\n' + str(exc))
