"""a9: edit Noark 5 run-profile technical steps, not raw JSON.

All changes are staged in the Setup dialog. Save/cancel is owned by Setup.
The immutable A200-A260 processing chain is displayed but not individually
switchable or movable; a7 builds it from selected technical operations.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QTextEdit, QVBoxLayout,
)

from app.run_profiles_v022_a9 import (
    MANDATORY_IDS, TECHNICAL_IDS, compose_profile_operations,
    stage_profile_edit, technical_operations,
)
from app.workflow_dependencies_v022_a7 import dependency_label
from app.operation_metadata import short_name


class RunProfileOrderEditor(QDialog):
    """One profile at a time; no in-place mutation of builtin templates."""

    def __init__(self, parent, *, settings: dict, profile):
        super().__init__(parent)
        self.settings = dict(settings)
        self.profile = profile
        self.result_edit = None
        self.setWindowTitle('Deljobber og rekkefølge – ' + profile.name)
        self.setMinimumSize(770, 660)
        layout = QVBoxLayout(self)
        intro = QLabel(
            'Merk av deljobber og flytt dem opp/ned. Arkade Noark og PRONOM er uavhengige. '
            'A130 må være med; evidens, dekningskontroll, rapport og KS-utkast '
            'legges automatisk etter de tekniske testene.', self)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addWidget(QLabel('Navn på ' + ('ny egen profil' if profile.builtin else 'egen profil') + ':'))
        self.name = QLineEdit(self)
        self.name.setMaxLength(100)
        self.name.setText(profile.name + ' – tilpasset' if profile.builtin else profile.name)
        layout.addWidget(self.name)

        row = QHBoxLayout()
        self.items = QListWidget(self)
        self.items.setAlternatingRowColors(True)
        row.addWidget(self.items, 1)
        buttons = QVBoxLayout()
        self.up = QPushButton('Flytt opp', self)
        self.down = QPushButton('Flytt ned', self)
        self.up.clicked.connect(lambda: self._move(-1))
        self.down.clicked.connect(lambda: self._move(1))
        buttons.addWidget(self.up)
        buttons.addWidget(self.down)
        buttons.addStretch(1)
        row.addLayout(buttons)
        layout.addLayout(row, 1)
        self.items.itemChanged.connect(self._preview)

        layout.addWidget(QLabel('Faktisk arbeidsflyt inkl. automatisk etterbehandling:'))
        self.preview = QTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(180)
        layout.addWidget(self.preview)
        self.note = QLabel(self)
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, self)
        self.save_button = footer.addButton(
            'Lagre som egen profil' if profile.builtin else 'Oppdater egen profil',
            QDialogButtonBox.ButtonRole.AcceptRole)
        self.save_button.clicked.connect(self._try_accept)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)

        original = technical_operations(profile)
        chosen = set(original)
        self.items.blockSignals(True)
        for op in (*original, *(op for op in TECHNICAL_IDS if op not in chosen)):
            item = QListWidgetItem(f'{dependency_label(op)}  {short_name(op, op)}', self.items)
            item.setData(Qt.ItemDataRole.UserRole, op)
            item.setToolTip(op)
            flags = item.flags()
            if op not in MANDATORY_IDS:
                flags |= Qt.ItemFlag.ItemIsUserCheckable
            else:
                flags &= ~Qt.ItemFlag.ItemIsUserCheckable
                item.setToolTip(op + ' – obligatorisk grunnlag for kanonisk evidens')
            item.setFlags(flags)
            item.setCheckState(Qt.CheckState.Checked if op in chosen else Qt.CheckState.Unchecked)
        self.items.blockSignals(False)
        if self.items.count():
            self.items.setCurrentRow(0)
        self._preview()

    def checked_technical(self) -> tuple[str, ...]:
        return tuple(str(self.items.item(i).data(Qt.ItemDataRole.UserRole))
                     for i in range(self.items.count())
                     if self.items.item(i).checkState() == Qt.CheckState.Checked)

    def _move(self, delta: int):
        index = self.items.currentRow()
        next_index = index + delta
        if not 0 <= index < self.items.count() or not 0 <= next_index < self.items.count():
            return
        self.items.blockSignals(True)
        item = self.items.takeItem(index)
        self.items.insertItem(next_index, item)
        self.items.setCurrentRow(next_index)
        self.items.blockSignals(False)
        self._preview()

    def _preview(self, _item=None):
        try:
            operations = compose_profile_operations(self.checked_technical())
        except ValueError as exc:
            self.preview.setPlainText('Arbeidsflyten er ikke gyldig ennå.')
            self.note.setText('Kan ikke lagre: ' + str(exc))
            self.save_button.setEnabled(False)
            return
        self.preview.setPlainText('\n'.join(
            f'{i:02d}  {dependency_label(op)}  {short_name(op, op)}'
            for i, op in enumerate(operations, 1)))
        self.note.setText(
            f'{len(self.checked_technical())} tekniske deljobber, '
            f'{len(operations) - len(self.checked_technical())} etterbehandlingsjobber. '
            'Verken Source, Work eller eksisterende jobber blir endret.')
        self.save_button.setEnabled(True)

    def _try_accept(self):
        try:
            self.result_edit = stage_profile_edit(
                self.settings, self.profile.profile_id, self.name.text(),
                self.checked_technical())
        except ValueError as exc:
            QMessageBox.warning(self, 'Ugyldig kjøreprofil', str(exc))
            return
        self.accept()
