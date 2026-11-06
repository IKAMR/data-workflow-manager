"""v0.1.10-a2: clearly explained Setup fields and visible storage-profile cards.

Pure Qt presentation. The shared Core role model and saved job paths are not
altered by opening Setup or switching a card. All persistence stays behind the
existing Save button and the v0.1.10-a1 Workbench API.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QRadioButton, QSizePolicy, QVBoxLayout, QWidget,
)

from app.storage_profiles_v0110_a1 import storage_profile_choices
from app.storage_profiles_v0110_a2 import profile_best_for, resolve_storage_profile
from gui_qt.setup_v0110_a1 import DwmSetupDialog as _A1SetupDialog
from gui_qt.setup_v018_a7 import DwmSetupDialog as _BaseSetupDialog


def _wrap(text: str, *, strong: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    if strong:
        label.setStyleSheet('font-weight: 600; color: #edf4fc;')
    return label


def _information(title: str, description: str) -> QFrame:
    """Full-width flow-layout message: no compressed form-row label to clip."""
    panel = QFrame()
    panel.setObjectName('dwmSetupInfo')
    panel.setStyleSheet(
        'QFrame#dwmSetupInfo {background: #192638; border: 1px solid #334d68;'
        'border-radius: 6px;}'
    )
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(15, 11, 15, 12)
    layout.setSpacing(5)
    layout.addWidget(_wrap(title, strong=True))
    layout.addWidget(_wrap(description))
    panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    return panel


class _ProfileCard(QFrame):
    """Keyboard-accessible radio selection with a large click target."""

    def __init__(self, title: str, description: str, recommended: bool = False):
        super().__init__()
        self.setObjectName('dwmStorageProfileCard')
        self.radio = QRadioButton()
        self.radio.setAccessibleName(title)
        self._recommended = recommended
        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 10, 13, 10)
        layout.setSpacing(5)
        header = QHBoxLayout()
        header.setSpacing(7)
        header.addWidget(self.radio, 0, Qt.AlignmentFlag.AlignTop)
        title_label = _wrap(title, strong=True)
        # The title wraps on laptops; the full card remains clickable.
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        header.addWidget(title_label, 1)
        layout.addLayout(header)
        if recommended:
            indicator = QLabel('STANDARD / ANBEFALT')
            indicator.setStyleSheet('color: #b7d9fb; font-size: 10px; font-weight: 600;')
            indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            layout.addWidget(indicator)
        note = _wrap(description)
        note.setStyleSheet('color: #bbcadc;')
        note.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(note)
        self.set_chosen(False)

    def set_chosen(self, chosen: bool) -> None:
        border = '#589ad7' if chosen else '#34465c'
        bg = '#243b56' if chosen else '#192434'
        self.setStyleSheet(
            'QFrame#dwmStorageProfileCard {'
            f'background: {bg}; border: 1px solid {border}; border-radius: 7px;'
            '}'
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.radio.setChecked(True)
            event.accept()
            return
        super().mousePressEvent(event)


class _ProfilePicker(QWidget):
    """Visible radio-card picker with currentData() for a1 Setup compatibility."""

    selectionChanged = Signal(str)

    def __init__(self, choices, active: str, parent=None):
        super().__init__(parent)
        self._choices = tuple(choices)
        self._cards = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        # Three visible choices in one compact row. Long labels wrap instead
        # of expanding the dialog; the surrounding Setup page is scrollable.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for item in self._choices:
            card = _ProfileCard(
                item.label,
                profile_best_for(item.profile_id) or item.description,
                recommended=item.profile_id == 'standard_enkel',
            )
            self._group.addButton(card.radio)
            self._cards[item.profile_id] = card
            layout.addWidget(card, 1)
            card.radio.toggled.connect(
                lambda checked, value=item.profile_id: self._on_toggled(value, checked)
            )
        if active not in self._cards:
            active = 'standard_enkel'
        self._cards[active].radio.setChecked(True)

    def currentData(self) -> str:
        for key, card in self._cards.items():
            if card.radio.isChecked():
                return key
        return 'standard_enkel'

    def _on_toggled(self, _value: str, checked: bool) -> None:
        if checked:
            current = self.currentData()
            for key, card in self._cards.items():
                card.set_chosen(key == current)
            self.selectionChanged.emit(current)


class DwmSetupDialog(_A1SetupDialog):
    """Keep a1 persistence and profile semantics; replace only two Setup pages."""

    def _build_general_tab(self):
        _content, form = self._tab('Generelt')
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(10, 9, 10, 9)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(1, 1)

        fields = (
            ('Temp-mappe (valgfritt):', 'temp_dir', 'Velg Temp-mappe',
             'Tomt = bruk standard midlertidig område'),
            ('Overordnet kjørelogg (valgfritt):', 'run_log_dir', 'Velg kjøreloggmappe',
             'Tomt = bruk vanlig plassering for kjørelogger'),
            ('Setup standardmappe (valgfritt):', 'setup_dir', 'Velg setup-mappe',
             'Tomt = bruk DWM-standardplassering'),
            ('Jobblister standardmappe (valgfritt):', 'job_list_dir', 'Velg jobblistemappe',
             'Tomt = bruk vanlig mappe for jobblister'),
        )
        for row, (label_text, key, title, placeholder) in enumerate(fields):
            editor = self._path_field(str(self.settings.get(key, '') or ''), title)
            editor.edit.setPlaceholderText(placeholder)
            editor.edit.setToolTip('Valgfritt. ' + placeholder + '.')
            setattr(self, key, editor)
            label = _wrap(label_text)
            grid.addWidget(label, row, 0, Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(editor, row, 1)

        grid.addWidget(_information(
            'Tomme mappefelt er helt i orden',
            'Du trenger ikke fylle ut noen av disse feltene. Når et felt er tomt, '
            'bruker DWM standardoppførselen for den funksjonen. Ingen arbeidsmapper '
            'opprettes bare fordi du åpner eller lagrer Setup.'
        ), len(fields), 0, 1, 2)

        backend = str(self.settings.get('execution_backend', 'local') or 'local')
        grid.addWidget(_wrap('Kjørebackend:'), len(fields) + 1, 0)
        backend_label = _wrap(f'{backend} (gjeldende innstilling; endres ikke her)')
        backend_label.setStyleSheet('color: #b9c8d9;')
        grid.addWidget(backend_label, len(fields) + 1, 1)
        form.addRow(body)

    def _build_storage_tab(self):
        _content, form = self._tab('Mapper og Work')
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 9, 10, 14)
        layout.setSpacing(13)

        layout.addWidget(_wrap('Velg standard lagringsprofil for NYE jobber', strong=True))
        layout.addWidget(_information(
            'Profilvalget endrer ikke eksisterende jobber',
            'DWM bruker profilen til å foreslå mapper når du oppretter en ny jobb. '
            'Eksisterende Source, Work, AIP, resultater og jobbidentiteter blir ikke '
            'flyttet eller endret når du velger en profil.'
        ))

        active = resolve_storage_profile(self.settings)
        self._storage_profile_choices = storage_profile_choices(include_legacy=active == 'none')
        self.storage_profile = _ProfilePicker(self._storage_profile_choices, active, self)
        layout.addWidget(self.storage_profile)

        summary = QFrame()
        summary.setObjectName('dwmProfileSummary')
        summary.setStyleSheet(
            'QFrame#dwmProfileSummary {background: #182535; border: 1px solid #35485d;'
            'border-radius: 6px;}'
        )
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(15, 13, 15, 13)
        summary_layout.setSpacing(7)
        summary_layout.addWidget(_wrap('VALGT PROFIL', strong=True))
        self.profile_title = _wrap('', strong=True)
        summary_layout.addWidget(self.profile_title)
        self.profile_description = _wrap('')
        summary_layout.addWidget(self.profile_description)
        self.profile_best_for = _wrap('')
        summary_layout.addWidget(self.profile_best_for)
        summary_layout.addWidget(_wrap('Påvirker: mappeforslag for nye jobber.'))
        summary_layout.addWidget(_wrap(
            'Påvirker ikke: eksisterende jobber, lagrede stier og Work-historikk.'
        ))
        layout.addWidget(summary)

        layout.addWidget(_wrap('Eksempel på mappestruktur', strong=True))
        self.profile_preview = QPlainTextEdit()
        self.profile_preview.setReadOnly(True)
        self.profile_preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.profile_preview.setFont(QFont('Consolas', 10))
        self.profile_preview.setMinimumHeight(180)
        self.profile_preview.setMaximumHeight(215)
        self.profile_preview.setToolTip('Kun et eksempel. DWM oppretter ikke disse mappene i Setup.')
        layout.addWidget(self.profile_preview)
        layout.addWidget(_wrap(
            'Forhåndsvisningen er illustrativ. Source leses uten endring. '
            'AIP er valgfritt ved testing og opprettes ikke av profilvalget.'
        ))

        layout.addWidget(_wrap('DWM-undermappe under Work – operations:', strong=True))
        self.work_subfolder = QLineEdit(str(self.settings.get('app_work_subfolder', 'dwm') or ''))
        self.work_subfolder.setPlaceholderText('Tomt = bruk Work – operations direkte')
        layout.addWidget(self.work_subfolder)
        layout.addWidget(_wrap(
            'Dette er en global regel, normalt «dwm». Jobblistens egen '
            'undermapperegel velges i Jobber-panelet. Ved endring kan eldre '
            'resultatstier påvirkes; DWM flytter ikke filer automatisk.'
        ))

        self.storage_profile.selectionChanged.connect(lambda _value: self._update_profile_preview())
        self.work_subfolder.textChanged.connect(lambda _value: self._update_profile_preview())
        self._update_profile_preview()
        form.addRow(body)

    def _update_profile_preview(self):
        selected = str(self.storage_profile.currentData() or 'standard_enkel')
        profile = next(
            (p for p in self._storage_profile_choices if p.profile_id == selected), None
        )
        if profile is None:
            self.profile_title.setText('Standard – enkel mappestruktur')
            self.profile_description.setText('Ukjent profilvalg. Standard brukes.')
            self.profile_best_for.setText('')
            self.profile_preview.setPlainText('Ingen kjent forhåndsvisning.')
            return
        self.profile_title.setText(profile.label)
        self.profile_description.setText(profile.description)
        best_for = profile_best_for(selected)
        self.profile_best_for.setText(('Passer når: ' + best_for) if best_for else '')
        subfolder = self.work_subfolder.text().strip()
        tree = profile.example_tree
        if subfolder:
            tree = tree.replace('dwm/', subfolder + '/')
        else:
            tree = '\n'.join(line for line in tree.splitlines() if 'dwm/' not in line)
            tree += '\n(DWM-data lagres direkte i Work-operasjonsmappen.)'
        self.profile_preview.setPlainText(tree)

    def _save(self):
        # Compare with the *effective* value. An unmarked old IKAMR default is
        # not a user-selected profile and needs no confusing change warning.
        previous = resolve_storage_profile(self.settings)
        selected = str(self.storage_profile.currentData() or 'standard_enkel')
        if selected != previous:
            answer = QMessageBox.question(
                self, 'Endre standard lagringsprofil',
                'Den nye profilen brukes kun for NYE jobber. Eksisterende '
                'Source, Work og AIP blir ikke flyttet eller endret. '
                'Vil du lagre profilvalget?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        # Call the original shared Save once, bypassing a1's redundant
        # raw-value comparison while retaining CLI / Work safety guards.
        _BaseSetupDialog._save(self)
