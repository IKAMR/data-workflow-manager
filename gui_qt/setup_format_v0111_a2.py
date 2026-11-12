"""Format assessment and external tooling in the existing DWM Setup.

External tools use full-width, independent sections rather than nested rows in
QFormLayout. SIARD Workflow Manager owns its Siegfried installation and
signatures; DWM discovers/uses the same executable without installing a copy.
"""
from __future__ import annotations

from queue import Empty, Queue
from threading import Thread

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from app.arkade5_setup_v018_a7 import find_arkade5_candidates
from app.siegfried_shared_v0111_a2 import find_siegfried_executable
from app.siegfried_tool_v0111_a3 import SiegfriedCheck, inspect_siegfried
from app.format_assessment_v0111_a2 import (
    DEFAULT_FORMAT_SOURCE, FORMAT_SOURCES, chosen_format_source,
)
from gui_qt.setup_v0110_a3 import DwmSetupDialog as _PreviousSetupDialog


def _full_width_note(text: str, parent=None) -> QLabel:
    """Selectable, wrapped text with no narrow form-label column."""
    label = QLabel(text, parent)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def _tool_section(stack: QVBoxLayout, title: str, explanation: str) -> QVBoxLayout:
    group = QGroupBox(title)
    group.setObjectName('dwm-external-tool-section')
    section = QVBoxLayout(group)
    section.setContentsMargins(18, 23, 18, 19)
    section.setSpacing(12)
    section.addWidget(_full_width_note(explanation, group))
    stack.addWidget(group)
    return section


def _toolbar(stack: QVBoxLayout, *buttons: QPushButton) -> None:
    """Keep command buttons on their own row; program path stays full width."""
    toolbar = QHBoxLayout()
    toolbar.setSpacing(9)
    for button in buttons:
        toolbar.addWidget(button)
    toolbar.addStretch(1)
    stack.addLayout(toolbar)


class DwmSetupDialog(_PreviousSetupDialog):
    def _tab(self, name):
        # Retain the original Setup tab; do not add a duplicate external tab.
        content, form = super()._tab(name)
        if name == 'Eksterne verktøy':
            self._siegfried_external_form = form  # old attribute, for compatibility
        return content, form

    def __init__(self, api, parent=None):
        super().__init__(api, parent)
        self._build_format_assessment_tab()
        self._build_siegfried_tools()

    def _build_external_tab(self):
        """Wide, scrollable Arkade/Siegfried tool cards like SIARD's tool setup.

        The inherited QFormLayout receives exactly ONE spanning widget. All
        path fields, buttons and status messages then use the full tab width.
        Existing inherited CLI callbacks and persistence are reused unchanged.
        """
        _content, form = self._tab('Eksterne verktøy')
        host = QWidget(self)
        stack = QVBoxLayout(host)
        stack.setContentsMargins(7, 10, 7, 15)
        stack.setSpacing(20)
        form.addRow(host)  # one spanning row, NOT narrow label/field pairs
        self._external_sections = stack

        stack.addWidget(_full_width_note(
            'Her kontrollerer du hvilke eksterne verktøy DWM kan bruke. '
            'Hvert verktøy har sin egen programsti, test og status. '
            'Ingen verktøy installeres eller kjøres mot arkivuttrekk fra Setup.',
            host,
        ))

        arkade = _tool_section(
            stack, 'Arkade 5 – Noark 5 og PRONOM',
            'DWM kan kjøre Arkade 5 CLI for Noark 5-tester og PRONOM/Siegfried. '
            'Tidligere Arkade-rapporter kan også importeres uten at CLI er installert.',
        )
        arkade.addWidget(_full_width_note('Programfil (Arkade 5 CLI)'))
        self.cli_path = QLineEdit(str(self.settings.get('arkade5_cli_path', '') or ''))
        self.cli_path.setPlaceholderText('Velg Arkivverket.Arkade.CLI.exe')
        arkade.addWidget(self.cli_path)

        choose = QPushButton('Bla gjennom…')
        choose.clicked.connect(self._browse_cli)
        detect = QPushButton('Finn automatisk')
        detect.clicked.connect(self._find_cli)
        self.test_cli_button = QPushButton('Test CLI / versjon')
        self.test_cli_button.clicked.connect(self._test_cli)
        _toolbar(arkade, choose, detect, self.test_cli_button)
        arkade.addWidget(_full_width_note('Status for Arkade 5 CLI'))
        self.cli_status = _full_width_note('Ikke testet i denne dialogen')
        arkade.addWidget(self.cli_status)
        self.cli_path.textChanged.connect(self._clear_test_status)

        arkade.addWidget(_full_width_note('Resultat-undermappe under Work'))
        self.arkade_output = QLineEdit(str(
            self.settings.get('arkade5_output_subfolder', 'arkade5_<ver>')
            or 'arkade5_<ver>'
        ))
        arkade.addWidget(self.arkade_output)
        arkade.addWidget(_full_width_note(
            'Gjelder kun Arkade-kjøringer fra DWM. Jobbens valgte Work-mappe '
            'og tidligere importert evidens endres ikke.',
        ))

    def _build_siegfried_tools(self):
        siegfried = _tool_section(
            self._external_sections, 'Siegfried – filidentifikasjon (PRONOM)',
            'Siegfried brukes til selvstendig identifikasjon av filformat. '
            'DWM finner normalt samme sf.exe som SIARD Workflow Manager har installert.',
        )
        siegfried.addWidget(_full_width_note('Programfil (sf.exe)'))
        self.sf_path = QLineEdit(str(self.settings.get('sf_executable') or ''))
        self.sf_path.setPlaceholderText(
            'Tomt felt: bruk delt SIARD-installasjon eller sf på PATH'
        )
        self.sf_path.setToolTip(
            'Egen programsti er valgfri. Tomt felt gir automatisk søk ved kjøring.'
        )
        siegfried.addWidget(self.sf_path)

        self.sf_browse_button = QPushButton('Bla gjennom…')
        self.sf_browse_button.clicked.connect(self._browse_siegfried)
        self.sf_find_button = QPushButton('Finn automatisk')
        self.sf_find_button.clicked.connect(self._find_siegfried)
        self.sf_test_button = QPushButton('Test / versjon')
        self.sf_test_button.clicked.connect(self._test_siegfried)
        _toolbar(siegfried, self.sf_browse_button, self.sf_find_button, self.sf_test_button)

        siegfried.addWidget(_full_width_note('Status for Siegfried'))
        self.sf_test_status = _full_width_note('Ikke testet i denne dialogen')
        siegfried.addWidget(self.sf_test_status)
        self.sf_signature_status = _full_width_note('PRONOM-signatur: ikke kontrollert')
        siegfried.addWidget(self.sf_signature_status)
        self.sf_path.textChanged.connect(self._clear_siegfried_status)

        shared = find_siegfried_executable()
        self.sf_discovery_status = _full_width_note(
            'Delt installasjon: ' + str(shared) if shared else
            'Delt installasjon: ikke funnet automatisk. Velg sf.exe manuelt '
            'eller installer Siegfried via SIARD Workflow Manager.'
        )
        siegfried.addWidget(self.sf_discovery_status)
        siegfried.addWidget(_full_width_note(
            'Installasjon og oppdatering av Siegfried og PRONOM-signaturene gjøres '
            'i SIARD Workflow Manager → Innstillinger → '
            'Programvare og avhengigheter. DWM bruker samme programfil uten kopiering.'
        ))
        self._sf_results: Queue[SiegfriedCheck] = Queue()
        self._sf_testing = False
        self._sf_timer = QTimer(self)
        self._sf_timer.setInterval(120)
        self._sf_timer.timeout.connect(self._read_siegfried_check)

    def _clear_siegfried_status(self, _text=''):
        if not self._sf_testing:
            self.sf_test_status.setText('Ny programsti valgt. Test / versjon for å kontrollere.')
            self.sf_signature_status.setText('PRONOM-signatur: ikke kontrollert')

    def _browse_siegfried(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, 'Velg Siegfried CLI (sf)', self.sf_path.text().strip(),
            'Siegfried (sf.exe sf);;Alle filer (*)',
        )
        if path:
            self.sf_path.setText(path)

    def _find_siegfried(self):
        found = find_siegfried_executable()
        if found:
            self.sf_path.setText(str(found))
            self.sf_discovery_status.setText('Delt installasjon: ' + str(found))
            self.sf_test_status.setText('Siegfried funnet. Test / versjon for å kontrollere.')
        else:
            self.sf_discovery_status.setText('Delt installasjon: ikke funnet')
            self.sf_test_status.setText(
                'Siegfried ble ikke funnet. Installer via SIARD Workflow Manager '
                'eller bla til sf.exe.'
            )

    def _test_siegfried(self):
        if self._sf_testing:
            return
        self._sf_testing = True
        self.sf_test_button.setEnabled(False)
        self.sf_test_status.setText('Sjekker Siegfried-versjon…')
        self.sf_signature_status.setText('PRONOM-signatur: kontrolleres…')
        executable = self.sf_path.text().strip()

        def run():
            try:
                result = inspect_siegfried(executable)
            except Exception as exc:
                result = SiegfriedCheck(ok=False, executable=executable,
                                        version='', signature='', message=str(exc))
            self._sf_results.put((executable, result))

        self._sf_timer.start()
        Thread(target=run, daemon=True).start()

    def _read_siegfried_check(self):
        try:
            requested_path, result = self._sf_results.get_nowait()
        except Empty:
            return
        self._sf_timer.stop()
        self._sf_testing = False
        self.sf_test_button.setEnabled(True)
        if requested_path != self.sf_path.text().strip():
            self.sf_test_status.setText('Programstien ble endret. Test på nytt.')
            self.sf_signature_status.setText('PRONOM-signatur: ikke kontrollert')
        elif result.ok:
            self.sf_test_status.setText('OK: ' + result.version + '\n' + result.executable)
            self.sf_signature_status.setText(
                'PRONOM-signatur: ' + (result.signature or 'Ikke oppgitt av Siegfried')
            )
        else:
            self.sf_test_status.setText('Ikke klar: ' + result.message)
            self.sf_signature_status.setText('PRONOM-signatur: ikke kontrollert')

    def _build_format_assessment_tab(self):
        _content, form = self._tab('Filformatvurdering')
        self.format_source = QComboBox(self)
        for key, label, _description in FORMAT_SOURCES:
            self.format_source.addItem(label, key)
        try:
            current = chosen_format_source(self.settings)
        except ValueError:
            current = DEFAULT_FORMAT_SOURCE
        index = self.format_source.findData(current)
        self.format_source.setCurrentIndex(max(0, index))
        form.addRow('Grunnlag for vurdering:', self.format_source)
        self.format_explanation = QLabel()
        self.format_explanation.setWordWrap(True)
        form.addRow('Hva betyr valget?', self.format_explanation)
        detail = QLabel(
            'Identifikasjon (PUID/format) og historisk Arkade-evidens beholdes '
            'uendret ved profilbytte. Nasjonalarkivets liste er en datert JSON-kopi; '
            'lokale vedtak og konkrete leveringsavtaler kan kreve egen vurdering. '
            'Egendefinerte versjonerte JSON-profiler kan fortsatt lastes inn '
            'fra PRONOM-visningen. Ingen AIP godkjennes automatisk.'
        )
        detail.setWordWrap(True)
        form.addRow('', detail)
        note = QLabel(
            'Siegfried konfigureres under Eksterne verktøy. Begge applikasjonene '
            'kan bruke samme installerte program; formatvurderingene holdes atskilt.'
        )
        note.setWordWrap(True)
        form.addRow('Siegfried / PRONOM:', note)
        self.format_source.currentIndexChanged.connect(self._update_format_description)
        self._update_format_description()

    def _update_format_description(self, _index=None):
        current = str(self.format_source.currentData() or '')
        description = next((item[2] for item in FORMAT_SOURCES if item[0] == current), '')
        self.format_explanation.setText(description)

    def _updates(self) -> dict:
        updates = super()._updates()
        updates['format_assessment_source'] = str(self.format_source.currentData() or '')
        updates['sf_executable'] = self.sf_path.text().strip()
        return updates
