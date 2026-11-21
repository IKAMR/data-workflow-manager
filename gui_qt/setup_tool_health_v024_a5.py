"""v0.2.4-a5: show automatically checked external tools in existing Setup.

This decorates the same Setup dialog installed by the v0.2.0/v0.2.2 hooks.
Never installs a program or edits Source, Work, evidence or job lists.
"""
from __future__ import annotations

from app.tool_health_v024_a5 import (
    ToolHealth, discover_arkade5, discover_siegfried, file_fingerprint, read_health_cache,
)


_REFERENCE_ARKADE = '2.13.1 (utgitt 23.09.2026, kontrollert 21.11.2026)'


def _describe(status: ToolHealth | None) -> str:
    if status is None:
        return 'Ikke kontrollert automatisk ennå.'
    label = {'ok': 'OK', 'warning': 'OBS', 'error': 'MANGLER/FEIL'}.get(status.state, 'Ukjent')
    if status.path and status.fingerprint and file_fingerprint(status.path) != status.fingerprint:
        label = 'MÅ KONTROLLERES PÅ NYTT'
    parts = [label + ': ' + (status.message or status.path or 'Ingen detaljer')]
    if status.path:
        parts.append('Fil: ' + status.path)
    if status.version:
        parts.append('Versjon: ' + status.version)
    if status.signature:
        parts.append('PRONOM-signatur: ' + status.signature)
    if status.tool == 'arkade5' and status.version:
        import re
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', status.version)
        if match and tuple(map(int, match.groups())) < (2, 13, 1):
            parts.append('OBS: Eldre enn dokumentert referanseversjon 2.13.1. ' 
                         'Oppdatering må gjøres manuelt.')
    if status.checked_at:
        parts.append('Sist kontrollert: ' + status.checked_at)
    return '\n'.join(parts)


def install_tool_health_setup() -> None:
    """Keep all existing Setup tabs, buttons, user edits and save behavior."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QInputDialog,
                                   QLabel, QPushButton, QVBoxLayout)
    from gui_qt import setup_format_v0111_a2 as module

    previous = module.DwmSetupDialog
    if getattr(previous, '_v024_a5_health_installed', False):
        return

    class SetupWithToolHealth(previous):
        _v024_a5_health_installed = True

        def __init__(self, api, parent=None):
            super().__init__(api, parent)
            box = QGroupBox('Automatisk oppstartskontroll – Arkade 5 og Siegfried')
            box.setObjectName('v024_a5_tool_health')
            layout = QVBoxLayout(box)
            intro = QLabel(
                'DWM søker i lagret Setup-sti, SIARD-installasjon, PATH, C:\\Prog, '
                'C:\\Program Files, C:\\Program Files (x86) og C:\\Programfiler. '
                'Verktøy testes uten å analysere arkivfiler. '
                'Resultater lagres per Windows-bruker og kan gjenbrukes ved ny DWM-versjon.'
            )
            intro.setWordWrap(True)
            layout.addWidget(intro)
            self.v024_a5_arkade_status = QLabel()
            self.v024_a5_arkade_status.setWordWrap(True)
            self.v024_a5_arkade_status.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            self.v024_a5_siegfried_status = QLabel()
            self.v024_a5_siegfried_status.setWordWrap(True)
            self.v024_a5_siegfried_status.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(QLabel('ARKADE 5 (CLI) – referanseversjon ' + _REFERENCE_ARKADE))
            layout.addWidget(self.v024_a5_arkade_status)
            layout.addWidget(QLabel('SIEGFRIED (sf.exe)'))
            layout.addWidget(self.v024_a5_siegfried_status)
            action_row = QHBoxLayout()
            recheck = QPushButton('Kontroller begge på nytt')
            recheck.setToolTip('Utfører en ny, ikke-blokkerende versjonskontroll. Ingen installasjon.')
            recheck.clicked.connect(self._v024_a5_recheck)
            action_row.addWidget(recheck)
            action_row.addStretch(1)
            layout.addLayout(action_row)
            self._external_sections.insertWidget(0, box)
            self._v024_a5_refresh_health()

        def _v024_a5_refresh_health(self):
            recorded = getattr(self.api, '_v024_a5_tool_health', None)
            if not isinstance(recorded, dict):
                recorded = read_health_cache()
            self.v024_a5_arkade_status.setText(_describe(recorded.get('arkade5')))
            self.v024_a5_siegfried_status.setText(_describe(recorded.get('siegfried')))
            if getattr(self.api, '_v024_a5_probe_running', False):
                self.v024_a5_arkade_status.setText(
                    self.v024_a5_arkade_status.text() + '\nNy kontroll pågår …')
                self.v024_a5_siegfried_status.setText(
                    self.v024_a5_siegfried_status.text() + '\nNy kontroll pågår …')

        def _v024_a5_recheck(self, _checked=False):
            window = self.parentWidget()
            if window is None:
                return
            from gui_qt.tool_health_startup_v024_a5 import schedule_tool_check
            schedule_tool_check(window, self.api, on_done=lambda _statuses: self._v024_a5_refresh_health())
            self._v024_a5_refresh_health()

        def _find_cli(self):
            from PySide6.QtWidgets import QMessageBox
            found = discover_arkade5()
            if not found:
                QMessageBox.information(
                    self, 'Arkade 5 CLI',
                    'Ingen Arkade 5 CLI ble funnet i installasjonsmapper eller PATH. '
                    'Last ned Arkade 5 CLI manuelt og velg programfilen. '
                    'Se https://arkade.nasjonalarkivet.no/ (ingen automatisk installasjon).')
                return
            items = [str(item) for item in found]
            choice, ok = QInputDialog.getItem(
                self, 'Arkade 5 CLI – funnet', 'Velg programfil:', items, 0, False)
            if ok and choice:
                self.cli_path.setText(choice)
                self.cli_status.setText('Programfil valgt. Trykk «Test CLI / versjon» og Lagre.')

        def _find_siegfried(self):
            from PySide6.QtWidgets import QMessageBox
            found = discover_siegfried()
            if not found:
                QMessageBox.information(
                    self, 'Siegfried',
                    'Fant ikke sf.exe i SIARD-installasjonen, PATH eller kjente installasjonsmapper. '
                    'Installer via SIARD Workflow Manager eller velg eksisterende sf.exe manuelt.')
                return
            names = [str(item) for item in found]
            choice, ok = QInputDialog.getItem(
                self, 'Siegfried – funnet', 'Velg programfil:', names, 0, False)
            if ok and choice:
                self.sf_path.setText(choice)
                self.sf_discovery_status.setText('Funnet programfil: ' + choice)
                self.sf_test_status.setText('Trykk «Test / versjon» og Lagre.')

    module.DwmSetupDialog = SetupWithToolHealth
