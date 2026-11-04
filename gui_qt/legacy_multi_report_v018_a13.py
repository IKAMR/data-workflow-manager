"""Qt selections for the existing a6 Noark 5 multi-extraction overview engine.

Unlike the old Tk version this accepts explicit Work snapshots, so report
selection does not depend on obsolete v4 .n5jobs layout or Source paths.
"""
from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QVBoxLayout,
)

from app.legacy_multi_report_v018_a13 import LegacyExportStopped, write_legacy_multi_report


SECTIONS = {
    "coverage": "Datadekning", "sources": "Kildesammenligning / mengdetall",
    "arkade_sources": "Arkade-kilder per import", "archive_parts": "Arkivdeler",
    "arkade_tests": "Arkade 5-tester", "pronom": "PRONOM og filformater",
    "deviations": "Registrerte avvik",
}
PROFILES = {
    "oversikt": (),
    "standard": ("coverage", "sources", "archive_parts", "arkade_tests", "deviations"),
    "detaljert": tuple(SECTIONS),
}


class LegacyMultiOverviewDialog(QDialog):
    def __init__(self, snapshots, *, parent=None):
        super().__init__(parent)
        self.shots = tuple(snapshots)
        self._pending: Thread | None = None
        self._events: Queue = Queue()
        self._stop = Event()
        self._last: Path | None = None
        self.setWindowTitle("Samlet uttrekksoversikt – klassisk Noark 5-rapport")
        self.setMinimumSize(700, 550)
        self.resize(860, 670)
        body = QVBoxLayout(self)
        note = QLabel(f"{len(self.shots)} valgte uttrekk. Skrivebeskyttet rapportgrunnlag fra de enkelte "
                      "Work-mappene. Den eksisterende a6-rapportmotoren brukes til sammenstilling "
                      "og kildesporbarhet. Ingen analyser kjøres på nytt.")
        note.setWordWrap(True)
        body.addWidget(note)
        info = QPlainTextEdit()
        info.setReadOnly(True)
        info.setMaximumHeight(112)
        info.setPlainText("\n".join(f"{s.job.job_id} – {s.job.name} | {s.job.work}"
                                     for s in self.shots))
        body.addWidget(info)
        fields = QFormLayout()
        self.profile = QComboBox()
        for label, value in (("Oversikt", "oversikt"), ("Standard", "standard"),
                             ("Detaljert", "detaljert")):
            self.profile.addItem(label, value)
        self.profile.setCurrentIndex(2)
        self.profile.currentIndexChanged.connect(self._preset)
        fields.addRow("Rapportprofil", self.profile)
        self.layout_choice = QComboBox()
        self.layout_choice.addItem("Én samlet rapport", "single")
        self.layout_choice.addItem("Hovedrapport + vedlegg per uttrekk", "attachments")
        fields.addRow("Rapportstruktur", self.layout_choice)
        body.addLayout(fields)
        group = QGroupBox("Velg innhold (kun HTML/PDF)")
        section_form = QVBoxLayout(group)
        self.section_checks = {}
        for key, label in SECTIONS.items():
            toggle = QCheckBox(label)
            toggle.setChecked(True)
            section_form.addWidget(toggle)
            self.section_checks[key] = toggle
        body.addWidget(group)
        target_fields = QFormLayout()
        self.prefix = QLineEdit()
        self.prefix.setPlaceholderText("Valgfritt filnavnprefiks")
        target_fields.addRow("Filnavnprefiks", self.prefix)
        target_bar = QHBoxLayout()
        self.target = QLineEdit()
        self.target.setPlaceholderText("Velg eksisterende rapportmappe")
        target_bar.addWidget(self.target, 1)
        browse = QPushButton("Velg mappe…")
        browse.clicked.connect(self._browse)
        target_bar.addWidget(browse)
        target_fields.addRow("Rapportmappe", target_bar)
        body.addLayout(target_fields)
        self.status = QLabel("Klar til rapportgenerering.")
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(100)
        body.addWidget(self.output)
        bar = QHBoxLayout()
        self.create = QPushButton("Lag klassisk samlerapport")
        self.create.clicked.connect(self._start)
        bar.addWidget(self.create)
        self.open_last = QPushButton("Åpne HTML")
        self.open_last.setEnabled(False)
        self.open_last.clicked.connect(self._open)
        bar.addWidget(self.open_last)
        bar.addStretch(1)
        self.close_button = QPushButton("Lukk")
        self.close_button.clicked.connect(self._close_or_stop)
        bar.addWidget(self.close_button)
        body.addLayout(bar)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.setInterval(150)

    def _preset(self, _index):
        keys = set(PROFILES[str(self.profile.currentData())])
        for key, checkbox in self.section_checks.items():
            checkbox.setChecked(key in keys)

    def _browse(self):
        directory = QFileDialog.getExistingDirectory(self, "Velg rapportmappe",
                                                      self.target.text() or str(Path.home()))
        if directory:
            self.target.setText(directory)

    def _start(self):
        if self._pending is not None:
            return
        target = Path(self.target.text().strip())
        if not self.target.text().strip() or not target.is_dir():
            QMessageBox.warning(self, "Rapport", "Velg en eksisterende eksportmappe.")
            return
        if any(s.depot is None for s in self.shots):
            QMessageBox.warning(self, "Rapport", "Minst ett uttrekk mangler lesbar depotrapport.")
            return
        prefix = self.prefix.text().strip()
        basename = (prefix + "_" if prefix else "") + "noark5-uttrekksoversikt"
        existing = [target / (basename + ending) for ending in (".html", ".json", ".csv", ".pdf")]
        overwrite = False
        if any(path.exists() for path in existing):
            reply = QMessageBox.question(
                self, "Eksisterende rapport", "Rapportfiler finnes i målmappen. "
                "Overskrive rapporter med dette prefikset?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        profile = str(self.profile.currentData())
        layout = str(self.layout_choice.currentData())
        sections = tuple(key for key, box in self.section_checks.items() if box.isChecked())
        self._stop.clear()
        self.create.setEnabled(False)
        self.close_button.setText("Stopp eksport")
        self.status.setText("Lager klassisk uttrekksoversikt fra lagrede Work-rapporter …")
        self.output.clear()

        def work():
            try:
                final, warnings = write_legacy_multi_report(
                    target, self.shots, prefix=prefix, profile=profile,
                    layout=layout, sections=sections, overwrite=overwrite, cancelled=self._stop)
                self._events.put(("complete", (final, warnings)))
            except LegacyExportStopped:
                self._events.put(("stopped", None))
            except Exception as exc:
                self._events.put(("failed", str(exc)))

        self._pending = Thread(target=work, daemon=True, name="dwm-a13-legacy-report")
        self._pending.start()
        self.timer.start()

    def _poll(self):
        while True:
            try:
                event, payload = self._events.get_nowait()
            except Empty:
                break
            self.timer.stop()
            self._pending = None
            self.create.setEnabled(True)
            self.close_button.setEnabled(True)
            self.close_button.setText("Lukk")
            if event == "complete":
                self._last, warnings = payload
                self.open_last.setEnabled(True)
                self.status.setText("Rapporten er laget: " + str(self._last))
                self.output.setPlainText("\n".join(warnings) if warnings else
                                         "HTML, JSON og CSV er laget. PDF forsøkes med legacy-motorens eksport.")
            elif event == "stopped":
                self.status.setText("Eksport stoppet før publisering.")
            else:
                self.status.setText("Rapporteksport feilet. Ingen nye kildedata endret.")
                self.output.setPlainText(str(payload))

    def _open(self):
        if self._last and self._last.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last)))

    def _close_or_stop(self):
        if self._pending is not None:
            self._stop.set()
            self.close_button.setEnabled(False)
            self.status.setText("Stopper før rapportfiler publiseres …")
        else:
            self.accept()

    def closeEvent(self, event):
        if self._pending is not None:
            self._close_or_stop()
            event.ignore()
        else:
            event.accept()
