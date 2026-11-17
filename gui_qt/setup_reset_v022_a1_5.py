"""Extend the EXISTING Setup reset, do not introduce a parallel settings store.

Requires install_setup_tab() from start_shell to have run first. The inherited
full reset (app.settings_portable.reset_settings) is retained unchanged.
"""
from __future__ import annotations


def install_setup_reset_actions() -> None:
    """Add a narrow startup reset and clarify the existing full-reset button."""
    from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton
    from gui_qt import setup_format_v0111_a2 as module
    from app.setup_reset_v022_a1_5 import restore_startup

    previous = module.DwmSetupDialog
    if getattr(previous, '_v022_a1_5_reset_installed', False):
        return

    class SetupWithReset(previous):
        _v022_a1_5_reset_installed = True

        def __init__(self, api, parent=None):
            super().__init__(api, parent)
            # A full Setup reset has existed since v0.1.8. Keep that action.
            self.reset_button.setText('Tilbakestill alle Setup-innstillinger…')
            self.reset_button.setToolTip(
                'Tilbakestill alle felles Setup-verdier, inkludert verktøystier og '
                'visning. Ingen jobblister, Source, Work eller rapporter slettes.'
            )
            page = self.startup_page
            note = QLabel(
                'Oppstart kan tilbakestilles uten å endre arbeidsprofil, '
                'verktøystier eller eksisterende kontroller.', page
            )
            note.setWordWrap(True)
            page.layout().addWidget(note)
            self.v022_reset_startup_button = QPushButton('Tilbakestill oppstart…', page)
            self.v022_reset_startup_button.setObjectName('v022_setup_reset_startup')
            self.v022_reset_startup_button.setToolTip(
                'Neste oppstart: Kontroll i Enkel modus. Depotprofil og jobber beholdes.'
            )
            self.v022_reset_startup_button.clicked.connect(self._v022_restore_startup)
            page.layout().addWidget(self.v022_reset_startup_button)

        def _v022_restore_startup(self):
            if self.api.running:
                QMessageBox.information(
                    self, 'Pågående jobb',
                    'Avslutt kjøringen før du tilbakestiller oppstartsinnstillingene.'
                )
                return
            choice = QMessageBox.question(
                self, 'Tilbakestill oppstart',
                'Vil du stille DWM tilbake til oppstart direkte i Enkel modus?\n\n'
                'Gjeldende arbeidsprofil, verktøystier, Source, Work, '
                'lagrede kontroller og rapporter beholdes.\n\n'
                'Eventuelle andre ulagrede endringer i dette Setup-vinduet forkastes.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
            try:
                restore_startup(self.api)
            except (OSError, ValueError, RuntimeError) as exc:
                QMessageBox.warning(self, 'Tilbakestilling feilet', str(exc))
                return
            QMessageBox.information(
                self, 'Oppstart tilbakestilt',
                'DWM åpner neste gang direkte i Kontroll / Enkel modus.\n'
                'Start DWM på nytt for å se effekten.'
            )
            self.accept()

    module.DwmSetupDialog = SetupWithReset
