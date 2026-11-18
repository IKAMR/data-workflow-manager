"""v0.2.2-a12: KS workshop entry in both Basic and Advanced mode.

The workshop dialog is imported only when opened by the operator; never
change the existing job runner or start-up native Qt safety configuration.
"""
from __future__ import annotations

from pathlib import Path

from gui_qt.main_v022_a11 import DwmMainWindow as _A11Window


class DwmMainWindow(_A11Window):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Legacy crash-regression tests create a Qt-free fake window.  Do not
        # import a real Qt module on that startup route.
        if not hasattr(self, '_toolbar'):
            return
        from PySide6.QtWidgets import QPushButton
        self.a12_ks_action = self._action(
            'Kvalitetssikring / godkjenningsrapport…', self._a12_open_ks_workshop)
        self.a12_ks_action.setToolTip(
            'Se alle lagrede tester og avvik, registrer faglige vurderinger, '
            'og lag et KS-rapportutkast for valgt jobb uten å kjøre tester på nytt.')
        self._toolbar.addAction(self.a12_ks_action)
        for top in self.menuBar().actions():
            menu = top.menu()
            if menu and menu.title().replace('&', '') == 'Rapport':
                menu.insertAction(menu.actions()[0], self.a12_ks_action) if menu.actions() else menu.addAction(self.a12_ks_action)
                break
        group = getattr(self, '_a2_step_groups', {}).get('run')
        if group is not None and group.layout() is not None:
            button = QPushButton('Kvalitetssikring / rapport…', group)
            button.setObjectName('a12_ks_basic')
            button.setToolTip('Åpne KS-arbeidsflate for valgt uttrekk, også etter fullført kontroll.')
            button.clicked.connect(self._a12_open_ks_workshop)
            group.layout().addWidget(button)
            self.a12_ks_basic_button = button
        self._a12_update_ks_controls()

    def _a12_update_ks_controls(self):
        if not hasattr(self, 'a12_ks_action'):
            return
        job_id = getattr(self, '_active_id', None)
        is_running = bool(getattr(self, '_worker', None)
                          or getattr(self.api, 'running', False)
                          or getattr(self, '_job_controls_running', False))
        enabled = bool(job_id and not is_running)
        self.a12_ks_action.setEnabled(enabled)
        button = getattr(self, 'a12_ks_basic_button', None)
        if button is not None:
            button.setEnabled(enabled)

    def _refresh(self, *args, **kwargs):
        outcome = super()._refresh(*args, **kwargs)
        self._a12_update_ks_controls()
        return outcome

    def _set_running_ui(self, running):
        outcome = super()._set_running_ui(running)
        self._a12_update_ks_controls()
        return outcome

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
            from gui_qt.ks_workshop_v022_a12 import KsWorkshopDialog
            dialog = KsWorkshopDialog(work, self)
            dialog.exec()
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kvalitetssikring',
                'KS-grunnlaget kunne ikke åpnes. Kontroller at jobbens A200–A260 '
                'og depotrapport er ferdige.\n\n' + str(exc))
