"""v0.2.0-a3: honest antivirus hand-off page, not a scanning implementation.

Selecting a folder, visiting this page or clicking Next MUST NOT assert that a
scan passed. No subprocess/AV provider is currently attached to this UI.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)


class AntivirusPage(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setObjectName('v020_a3_antivirus_page')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(27, 22, 27, 24)
        header = QHBoxLayout()
        title = QLabel('Antiviruskontroll')
        title.setStyleSheet('font-size: 22px; font-weight: 600;')
        header.addWidget(title)
        header.addStretch()
        back = QPushButton('Til Startside')
        back.clicked.connect(lambda: window.v020_integrated_home())
        header.addWidget(back)
        layout.addLayout(header)
        status = QLabel('Status: IKKE SKANNET – ingen antivirusmotor er koblet til DWM')
        status.setObjectName('v020_a3_antivirus_status')
        status.setWordWrap(True)
        layout.addWidget(status)
        help_text = QLabel(
            'Dette trinnet er klargjort for senere integrasjon. Velg eventuelt en '
            'mottaks- eller karantenemappe for å vise hvilken mappe som skal '
            'kontrolleres i depotets godkjente antivirusløsning. DWM utfører '
            'ikke antiviruskontroll, endrer ingen filer og registrerer ikke '
            'en godkjent skanning i denne versjonen.'
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setReadOnly(True)
        self.folder.setPlaceholderText('Ingen mappe valgt')
        self.folder.setObjectName('v020_a3_antivirus_folder')
        row.addWidget(self.folder, 1)
        choose = QPushButton('Velg mappe…')
        choose.clicked.connect(self._choose_folder)
        row.addWidget(choose)
        layout.addLayout(row)
        note = QLabel(
            'En valgt mappe er ikke en skanneresultathendelse. Skanningsdato, '
            'motor, signaturversjon og resultat må først komme fra en verifisert '
            'skannerintegrasjon før DWM kan registrere status.'
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, 'Velg mappe for ekstern antiviruskontroll', self.folder.text()
        )
        if folder:
            self.folder.setText(folder)
        # Intentionally no scan, status mutation or audit event.
