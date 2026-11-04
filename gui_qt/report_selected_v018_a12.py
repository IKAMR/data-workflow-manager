"""Qt adapter to DWM's existing a20 multi-job report exporter.

No report renderer lives here. This is a presentation/selection boundary only:
read-only job snapshots -> established report service -> user-chosen folder.
"""
from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread

from PySide6.QtCore import QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.application_api import DwmApiError
from noark5_workflow.reporting.job_summary_a16 import PRESETS, SECTIONS, ReportOptions


class SelectedReportDialog(QDialog):
    """One or many Noark 5 jobs; SIARD jobs are visible but not reportable."""

    def __init__(self, api, *, active_job_id: str | None = None, parent=None):
        super().__init__(parent)
        self.api = api
        self._settings = QSettings("IKAMR", "DWM-Qt")
        self._events: Queue[tuple[str, object]] = Queue()
        self._overwrite_reply: Queue[bool] = Queue(maxsize=1)
        self._stop = Event()
        self._worker: Thread | None = None
        self._last_report: Path | None = None
        self.setWindowTitle("Rapport – ett eller flere Noark 5-uttrekk")
        self.resize(850, 760)
        self.setMinimumSize(720, 570)
        body = QVBoxLayout(self)
        explanation = QLabel(
            "Velg én eller flere jobber. Bruker lagrede resultater fra hver jobbs Work. "
            "Rapporten lager ikke nye analyser og endrer ikke jobbstatus. "
            "SIARD holdes adskilt til rapportmotoren støtter den uttrekkstypen."
        )
        explanation.setWordWrap(True)
        body.addWidget(explanation)

        self.jobs = QTableWidget(0, 4, self)
        self.jobs.setHorizontalHeaderLabels(["Velg", "Jobb", "Uttrekk", "Profil / status"])
        self.jobs.verticalHeader().setVisible(False)
        self.jobs.setAlternatingRowColors(True)
        self.jobs.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.jobs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.jobs.horizontalHeader().setStretchLastSection(True)
        self.jobs.setColumnWidth(0, 57)
        self.jobs.setColumnWidth(1, 92)
        self.jobs.setColumnWidth(2, 360)
        self._candidates = self.api.report_candidates()
        self.jobs.setRowCount(len(self._candidates))
        for row, job in enumerate(self._candidates):
            choice = QTableWidgetItem("")
            choice.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            choice.setCheckState(
                Qt.CheckState.Checked if job["enabled"] and job["job_id"] == active_job_id
                else Qt.CheckState.Unchecked
            )
            if not job["enabled"]:
                choice.setFlags(Qt.ItemFlag.NoItemFlags)
                choice.setToolTip("Eksisterende samlerapport gjelder bare Noark 5-jobber.")
            self.jobs.setItem(row, 0, choice)
            for col, label in enumerate((job["job_id"], job["name"],
                                         (job["profile_id"] or "Profil ikke valgt") + " · " + job["status"]), 1):
                self.jobs.setItem(row, col, QTableWidgetItem(str(label)))
        body.addWidget(self.jobs, 2)
        controls = QHBoxLayout()
        choose_all = QPushButton("Velg alle Noark 5-jobber")
        choose_all.clicked.connect(lambda: self._choose_jobs(True))
        controls.addWidget(choose_all)
        choose_none = QPushButton("Fjern valg")
        choose_none.clicked.connect(lambda: self._choose_jobs(False))
        controls.addWidget(choose_none)
        controls.addStretch(1)
        body.addLayout(controls)

        group = QGroupBox("Rapportinnhold")
        grid = QGridLayout(group)
        grid.addWidget(QLabel("Detaljnivå"), 0, 0)
        self.level = QComboBox()
        self.level.addItems(list(PRESETS))
        self.level.setCurrentText("Medium")
        self.level.currentTextChanged.connect(self._preset_changed)
        grid.addWidget(self.level, 0, 1, 1, 2)
        self.sections: dict[str, QCheckBox] = {}
        for i, (name, label) in enumerate(SECTIONS.items()):
            checkbox = QCheckBox(label)
            checkbox.setChecked(name in PRESETS["Medium"])
            grid.addWidget(checkbox, 1 + i // 3, i % 3)
            self.sections[name] = checkbox
        self.extraction = QCheckBox("Vedlegg per uttrekk")
        self.archive_parts = QCheckBox("Vedlegg per arkivdel")
        grid.addWidget(self.extraction, 4, 0, 1, 2)
        grid.addWidget(self.archive_parts, 4, 2)
        body.addWidget(group)

        formats = QHBoxLayout()
        formats.addWidget(QLabel("Eksportformat:"))
        self.formats: dict[str, QCheckBox] = {}
        for name in ("HTML", "PDF", "JSON", "CSV"):
            toggle = QCheckBox(name)
            toggle.setChecked(name == "HTML")
            formats.addWidget(toggle)
            self.formats[name.lower()] = toggle
        formats.addStretch(1)
        body.addLayout(formats)

        target_form = QGridLayout()
        target_form.addWidget(QLabel("Filnavnprefiks (valgfritt)"), 0, 0)
        self.prefix = QLineEdit()
        self.prefix.setPlaceholderText("Eksempel: 1502_ephorte_hist")
        target_form.addWidget(self.prefix, 0, 1, 1, 2)
        target_form.addWidget(QLabel("Eksportmappe"), 1, 0)
        self.target = QLineEdit(str(self._settings.value("qt/a12_report_target", "") or ""))
        target_form.addWidget(self.target, 1, 1)
        browse = QPushButton("Velg mappe…")
        browse.clicked.connect(self._choose_target)
        target_form.addWidget(browse, 1, 2)
        body.addLayout(target_form)

        self.state = QLabel("Samlerapporten er skrivebeskyttet overfor jobber og uttrekk.")
        self.state.setWordWrap(True)
        body.addWidget(self.state)
        self.messages = QPlainTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setMaximumBlockCount(350)
        body.addWidget(self.messages, 1)
        buttons = QHBoxLayout()
        self.start = QPushButton("Lag og åpne rapport")
        self.start.clicked.connect(self._start_export)
        buttons.addWidget(self.start)
        self.open_last = QPushButton("Åpne siste eksport")
        self.open_last.setEnabled(False)
        self.open_last.clicked.connect(self._open_latest)
        buttons.addWidget(self.open_last)
        buttons.addStretch(1)
        self.cancel = QPushButton("Lukk")
        self.cancel.clicked.connect(self._cancel_or_close)
        buttons.addWidget(self.cancel)
        body.addLayout(buttons)
        self._timer = QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._poll)

    def _choose_jobs(self, checked: bool):
        for row, job in enumerate(self._candidates):
            if job["enabled"]:
                self.jobs.item(row, 0).setCheckState(
                    Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )

    def _preset_changed(self, value: str):
        enabled = set(PRESETS.get(value, ()))
        for key, toggle in self.sections.items():
            toggle.setChecked(key in enabled)

    def _choose_target(self):
        selected = QFileDialog.getExistingDirectory(
            self, "Velg eksportmappe", self.target.text().strip() or str(Path.home()),
        )
        if selected:
            self.target.setText(selected)

    def _selected_ids(self) -> tuple[str, ...]:
        return tuple(job["job_id"] for row, job in enumerate(self._candidates)
                     if job["enabled"] and self.jobs.item(row, 0).checkState() == Qt.CheckState.Checked)

    @staticmethod
    def _protected_destination(directory: Path, jobs) -> str:
        """No generated report files may be placed *inside* Source or AIP."""
        target = directory.resolve(strict=False)
        for job in jobs:
            for key, label in (("active_extraction_root", "Source"),
                               ("archive_root", "AIP"), ("output_root", "AIP")):
                value = getattr(job, key, None)
                if value:
                    source = Path(value).resolve(strict=False)
                    if target == source or source in target.parents:
                        return "Eksportmappen ligger i " + label + " for " + job.job_id + ". Velg en annen mappe."
        return ""

    def _start_export(self):
        if self._worker is not None:
            return
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(self, "Rapport", "Velg én eller flere Noark 5-jobber.")
            return
        selected = tuple(name for name, box in self.sections.items() if box.isChecked())
        formats = tuple(name for name, box in self.formats.items() if box.isChecked())
        if not selected or not formats:
            QMessageBox.warning(self, "Rapport", "Velg minst én rapportdel og ett eksportformat.")
            return
        folder = Path(self.target.text().strip())
        if not self.target.text().strip() or not folder.is_dir():
            QMessageBox.warning(self, "Rapport", "Velg en eksisterende eksportmappe.")
            return
        try:
            jobs = self.api.selected_report_jobs(ids)
            unsafe = self._protected_destination(folder, jobs)
            if unsafe:
                raise DwmApiError(unsafe)
            options = ReportOptions(self.level.currentText(), selected,
                                    self.extraction.isChecked(), self.archive_parts.isChecked())
        except (DwmApiError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Rapport", str(exc))
            return
        self._settings.setValue("qt/a12_report_target", str(folder))
        self._stop.clear()
        self.start.setEnabled(False)
        self.cancel.setText("Stopp eksport")
        self.state.setText("Genererer rapport fra lagrede Work-resultater …")
        self.messages.appendPlainText("Starter rapport: " + ", ".join(ids))
        while not self._overwrite_reply.empty():
            try:
                self._overwrite_reply.get_nowait()
            except Empty:
                break

        # Capture every Qt widget value before starting a worker. Qt widgets
        # must never be accessed from a Python background thread.
        export_prefix = self.prefix.text().strip()
        def worker_safe():
            def progress(stage, message, done, total, log_path):
                self._events.put(("progress", (str(stage), str(message), int(done), int(total), str(log_path))))
            def confirm(paths):
                self._events.put(("overwrite", tuple(map(str, paths))))
                while not self._stop.is_set():
                    try:
                        return self._overwrite_reply.get(timeout=0.20)
                    except Empty:
                        continue
                return False
            try:
                from noark5_workflow.reporting.report_recovery_a203 import (
                    ExportStopped, write_reconnectable_report,
                )
                from noark5_workflow.reporting.report_service_a20 import write_report_package
                result = write_reconnectable_report(
                    folder, jobs, options, prefix=export_prefix,
                    formats=formats, cancelled=self._stop, on_progress=progress,
                    on_warning=lambda text: self._events.put(("warning", str(text))),
                    confirm_overwrite=confirm, writer=write_report_package,
                )
                self._events.put(("done", str(result)))
            except Exception as exc:
                # Import is optional until the operator starts an export. If
                # the recovery service requested cancellation, distinguish it
                # from a report/rendering failure without masking other errors.
                if type(exc).__name__ == "ExportStopped":
                    self._events.put(("stopped", "Rapporteksport avbrutt."))
                else:
                    self._events.put(("error", str(exc)))

        self._worker = Thread(target=worker_safe, daemon=True, name="dwm-a12-report-export")
        self._worker.start()
        self._timer.start()

    def _poll(self):
        for _ in range(100):
            try:
                kind, payload = self._events.get_nowait()
            except Empty:
                break
            if kind == "progress":
                stage, message, done, total, logfile = payload
                self.state.setText(message)
                self.messages.appendPlainText(f"{stage}: {message}" + (f" ({done}/{total})" if total else ""))
            elif kind == "overwrite":
                names = tuple(payload)
                prompt = "Rapportfiler finnes fra før. Overskrive?\n\n" + "\n".join(names[:5])
                accepted = QMessageBox.question(
                    self, "Bekreft overskriving", prompt,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                ) == QMessageBox.StandardButton.Yes
                self._overwrite_reply.put(accepted)
            elif kind == "warning":
                self.messages.appendPlainText("MERKNAD: " + str(payload))
            elif kind in {"done", "stopped", "error"}:
                self._timer.stop()
                self._worker = None
                self.cancel.setText("Lukk")
                self.cancel.setEnabled(True)
                self.start.setEnabled(True)
                if kind == "done":
                    self._last_report = Path(payload)
                    self.open_last.setEnabled(True)
                    self.state.setText("Rapport lagret: " + str(payload))
                    self.messages.appendPlainText("FERDIG: " + str(payload))
                    self._open_latest()
                elif kind == "error":
                    self.state.setText("Rapporteksport feilet: " + str(payload))
                    self.messages.appendPlainText("FEIL: " + str(payload))
                else:
                    self.state.setText(str(payload))
                break

    def _open_latest(self):
        if self._last_report is not None and self._last_report.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_report)))

    def _cancel_or_close(self):
        if self._worker is not None:
            self._stop.set()
            self.cancel.setEnabled(False)
            self.state.setText("Stopper etter pågående filoperasjon …")
        else:
            self.accept()

    def closeEvent(self, event):
        if self._worker is not None:
            self._cancel_or_close()
            event.ignore()
        else:
            event.accept()
