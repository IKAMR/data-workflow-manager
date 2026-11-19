"""v0.2.3-a3: KS source-value census and authoritative period-source comparison.

No changes to normal job execution, window layout, or advanced mode.
"""
from __future__ import annotations

from pathlib import Path
from gui_qt.main_v023_a2 import DwmMainWindow as _A2Window


class DwmMainWindow(_A2Window):
    def _a12_open_ks_workshop(self, _checked=False):
        from PySide6.QtWidgets import QMessageBox
        if (getattr(self, '_worker', None) is not None or self.api.running
                or getattr(self, '_job_controls_running', False)):
            QMessageBox.information(self, 'Kvalitetssikring',
                                    'Avslutt pågående jobb før du registrerer faglige vurderinger.')
            return
        if not self._active_id:
            QMessageBox.information(self, 'Kvalitetssikring', 'Velg et uttrekk i jobblisten først.')
            return
        try:
            work = getattr(self.api.job_details(self._active_id).job, 'effective_work_operations', None)
            if not work or not Path(work).is_dir():
                raise ValueError('Valgt jobb har ikke en tilgjengelig Work-mappe')
            from gui_qt.ks_value_inspection_v023_a3 import KsWorkshopDialog
            KsWorkshopDialog(work, self).exec()
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kvalitetssikring',
                                'KS-grunnlaget kunne ikke åpnes. Kontroller A200–A260 og rapportgrunnlaget.\n\n'
                                + str(exc))
