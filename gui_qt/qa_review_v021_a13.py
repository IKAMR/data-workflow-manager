"""Qt integration for a13 QA/depot reports within Resultatvisninger -> Depotvurdering.

Uses the established result-center panel and Work-job identity. The existing
Qt a20 selected-job report dialog, report engine and depot decision APIs are
not replaced. All new annotation writes are explicit user actions.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from PySide6.QtCore import Qt, QSettings, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from noark5_workflow.reporting.qa_decision_v021_a12 import build_snapshot, ReportInputError
from noark5_workflow.reporting.qa_decision_v021_a13 import export_review_bundle
from noark5_workflow.reporting.qa_review_v021_a13 import (
    STATUSES, finding_key, latest_reviews, record_review,
)


class QaFindingReviewDialog(QDialog):
    """One-job human review, with explicit recipient selection for comments."""

    def __init__(self, panel, row, parent=None):
        super().__init__(parent)
        self._panel = panel
        self._row = row
        self._work = Path(str((row.details or {}).get("work_root") or ""))
        if not self._work.is_dir() or not (self._work / "job.json").is_file():
            raise ReportInputError("Valgt omfang mangler gyldig DWM Work-jobb")
        if not row.report_path or not row.report_path.is_file():
            raise ReportInputError("Valgt omfang mangler original depotrapport")
        self._depot_path = row.report_path.relative_to(self._work).as_posix()
        self._settings = QSettings("IKAMR", "DWM-Qt")
        self._kdrs_path: Path | None = None
        self._snapshot: dict = {}
        self._findings: list[dict] = []
        self._current_reviews: dict = {}
        self._active_key: str | None = None
        self._loading_form = False
        self._dirty = False
        self._worker: Thread | None = None
        self._events: Queue = Queue()
        self._last_export: Path | None = None
        self.setWindowTitle("KS / depot – vurder funn – " + row.job_id)
        self.resize(1120, 780)
        self.setMinimumSize(800, 600)
        outer = QVBoxLayout(self)
        note = QLabel(
            "Valgt DWM-jobb: " + row.job_id + " · Faglige kommentarer er egne Work-hendelser. "
            "De endrer ikke teknisk teststatus, Arkade/KDRS-evidens eller depotvedtak. "
            "Bare kommentarer valgt til rapportering eksporteres."
        )
        note.setWordWrap(True)
        outer.addWidget(note)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Nivå:"))
        self.severity = QComboBox(self)
        self.severity.addItem("Alle", "")
        for level in ("ERROR", "WARNING", "REVIEW", "NOTE", "INFORMATION"):
            self.severity.addItem(level, level)
        self.severity.currentIndexChanged.connect(self._filter)
        filters.addWidget(self.severity)
        filters.addWidget(QLabel("Søk:"))
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Test-ID, kilde, arkivdel eller melding")
        self.search.textChanged.connect(self._filter)
        filters.addWidget(self.search, 1)
        self.reload = QPushButton("Oppdater funn", self)
        self.reload.clicked.connect(self._reload)
        filters.addWidget(self.reload)
        outer.addLayout(filters)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.table = QTableWidget(0, 5, splitter)
        self.table.setHorizontalHeaderLabels(("Nivå", "Test-ID", "Kilde", "Beskrivelse", "Faglig status"))
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for col, width in ((0, 90), (1, 160), (2, 145), (4, 165)):
            self.table.setColumnWidth(col, width)
        self.table.itemSelectionChanged.connect(self._choose_finding)
        splitter.addWidget(self.table)
        editor = QWidget(splitter)
        form = QVBoxLayout(editor)
        form.addWidget(QLabel("Kildedetaljer (skrivebeskyttet):"))
        self.details = QPlainTextEdit(editor)
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(128)
        form.addWidget(self.details)
        row_status = QHBoxLayout()
        row_status.addWidget(QLabel("Faglig vurdering:"))
        self.status = QComboBox(editor)
        for code, label in STATUSES.items():
            self.status.addItem(label, code)
        self.status.currentIndexChanged.connect(self._mark_dirty)
        row_status.addWidget(self.status, 1)
        self.include_ks = QCheckBox("Ta med kommentaren i KS-rapport", editor)
        self.include_ks.setChecked(True)
        self.include_ks.toggled.connect(self._mark_dirty)
        row_status.addWidget(self.include_ks)
        self.include_depot = QCheckBox("Ta med i depotrapport", editor)
        self.include_depot.setChecked(True)
        self.include_depot.toggled.connect(self._mark_dirty)
        row_status.addWidget(self.include_depot)
        form.addLayout(row_status)
        form.addWidget(QLabel("Faglig kommentar / begrunnelse:"))
        self.comment = QPlainTextEdit(editor)
        self.comment.setPlaceholderText("Beskriv hva som er undersøkt, betydningen av funnet og eventuell oppfølging.")
        self.comment.setMaximumHeight(115)
        self.comment.textChanged.connect(self._mark_dirty)
        form.addWidget(self.comment)
        actions = QHBoxLayout()
        self.save = QPushButton("Lagre faglig merknad", editor)
        self.save.clicked.connect(self._save_review)
        actions.addWidget(self.save)
        actions.addStretch(1)
        form.addLayout(actions)
        splitter.addWidget(editor)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 5)
        outer.addWidget(splitter, 1)

        export = QHBoxLayout()
        self.kdrs_label = QLabel("a11 KDRS QA: ikke valgt (valgfritt)")
        self.kdrs_label.setWordWrap(True)
        export.addWidget(self.kdrs_label, 1)
        choose_qa = QPushButton("Velg a11 KDRS QA…")
        choose_qa.clicked.connect(self._choose_qa)
        export.addWidget(choose_qa)
        outer.addLayout(export)
        target = QHBoxLayout()
        target.addWidget(QLabel("Ny rapportmappe:"))
        self.out = QLineEdit(self)
        self.out.setPlaceholderText("Velg en overordnet katalog, så foreslås en ny undermappe")
        target.addWidget(self.out, 1)
        choose_dir = QPushButton("Velg mål…", self)
        choose_dir.clicked.connect(self._choose_destination)
        target.addWidget(choose_dir)
        outer.addLayout(target)
        footer = QHBoxLayout()
        self.generate = QPushButton("Lag KS + depot + Full-rapport (a20)", self)
        self.generate.clicked.connect(self._generate)
        footer.addWidget(self.generate)
        self.pdf = QCheckBox("Inkluder PDF (a20)", self)
        footer.addWidget(self.pdf)
        self.open_last = QPushButton("Åpne siste rapportpakke", self)
        self.open_last.setEnabled(False)
        self.open_last.clicked.connect(self._open_last)
        footer.addWidget(self.open_last)
        footer.addStretch(1)
        self.close_button = QPushButton("Lukk", self)
        self.close_button.clicked.connect(self.reject)
        footer.addWidget(self.close_button)
        outer.addLayout(footer)
        self.message = QLabel("Lagring og eksport gjør ingen nye Noark-, XPath- eller Arkade-kjøringer.")
        self.message.setWordWrap(True)
        outer.addWidget(self.message)
        self._timer = QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._poll)
        self._reload()

    def _mark_dirty(self, *_args):
        if not self._loading_form:
            self._dirty = True

    def _uncommitted(self) -> bool:
        if not self._dirty:
            return False
        result = QMessageBox.question(
            self, "Ulagret kommentar", "Forkast endringer som ikke er lagret?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result != QMessageBox.StandardButton.Yes

    def _reload(self):
        if self._uncommitted():
            return
        try:
            candidate = build_snapshot(
                work=self._work, depot_report=self._depot_path, kdrs_qa=self._kdrs_path)
            findings = list(candidate["findings"])
            current = latest_reviews(self._work, candidate)["current"]
        except (ValueError, OSError, ReportInputError) as exc:
            QMessageBox.warning(self, "Kontrollgrunnlag", str(exc))
            return False
        self._snapshot = candidate
        self._findings = findings
        self._current_reviews = current
        self._active_key = None
        self._dirty = False
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._findings))
        for i, item in enumerate(self._findings):
            key = finding_key(item)
            saved = self._current_reviews.get(key)
            values = (item["severity"], item["test_id"], item["source"],
                      item["message"], STATUSES.get(saved["status"], "Ikke vurdert") if saved else "Ikke vurdert")
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setToolTip(str(value))
                if col == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, i)
                self.table.setItem(i, col, cell)
        self.table.blockSignals(False)
        self._filter()
        if self._findings:
            self.table.selectRow(0)
            self._choose_finding()
        else:
            self.details.setPlainText("Ingen observerte funn i valgt rapportgrunnlag. Dette er ikke en godkjenning.")
        self.message.setText(f"{len(self._findings)} kildefunn · {len(self._current_reviews)} faglig vurdert. "
                             "Valgt rapportversjon er skrivebeskyttet.")
        return True

    def _filter(self, *_args):
        needle = self.search.text().strip().casefold()
        level = self.severity.currentData() or ""
        for index, finding in enumerate(self._findings):
            haystack = " ".join(str(finding.get(k) or "") for k in
                                ("test_id", "source", "message", "context", "file")).casefold()
            self.table.setRowHidden(index,
                                    bool(level and finding["severity"] != level) or bool(needle and needle not in haystack))

    def _choose_finding(self):
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            return
        index = selection[0].row()
        if index < 0 or index >= len(self._findings):
            return
        finding = self._findings[index]
        key = finding_key(finding)
        if key != self._active_key and self._uncommitted():
            self.table.blockSignals(True)
            for row, candidate in enumerate(self._findings):
                if finding_key(candidate) == self._active_key:
                    self.table.selectRow(row)
                    break
            self.table.blockSignals(False)
            return
        if key == self._active_key:
            return
        self._active_key = key
        lines = ", ".join(str(x) for x in finding.get("lines") or [])
        self.details.setPlainText(
            "Test: " + str(finding.get("test_id")) + " | Kilde: " + str(finding.get("source")) +
            " | Nivå: " + str(finding.get("severity")) + "\n" + str(finding.get("message")) +
            "\nArkivdel/kontekst: " + str(finding.get("context") or "Ikke dokumentert") +
            "\nFil/linje: " + str(finding.get("file") or "Ikke dokumentert") + " " + lines +
            "\nEvidens: " + str(finding.get("source_ref") or "Ikke dokumentert"))
        saved = self._current_reviews.get(key)
        self._loading_form = True
        try:
            self.status.setCurrentIndex(self.status.findData(saved["status"]) if saved else 0)
            self.comment.setPlainText(saved["comment"] if saved else "")
            self.include_ks.setChecked(bool(saved["include_in_ks"]) if saved else True)
            self.include_depot.setChecked(bool(saved["include_in_depot"]) if saved else True)
        finally:
            self._loading_form = False
            self._dirty = False

    def _save_review(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._findings):
            QMessageBox.information(self, "Faglig vurdering", "Velg et konkret funn først.")
            return
        user = self._panel._identity()  # Reuses the existing depot profile dialog.
        if user is None:
            return
        finding = self._findings[row]
        try:
            event = record_review(
                self._work, self._snapshot, finding,
                status=self.status.currentData(), comment=self.comment.toPlainText(),
                user=user, include_in_ks=self.include_ks.isChecked(),
                include_in_depot=self.include_depot.isChecked(),
            )
            self._current_reviews[event["finding_key"]] = event
            self.table.item(row, 4).setText(STATUSES[event["status"]])
            self._dirty = False
            self.message.setText("Lagret faglig merknad (ikke depotvedtak): " + event["event_id"])
        except (OSError, ValueError, ReportInputError) as exc:
            QMessageBox.warning(self, "Kunne ikke lagre", str(exc))

    def _choose_qa(self):
        if self._uncommitted():
            return
        selected, _ = QFileDialog.getOpenFileName(
            self, "Velg noark5-a11-practical-qa.json", str(self._settings.value("qt/a13_qa_path", "") or ""),
            "JSON (*.json)")
        if selected:
            previous = self._kdrs_path
            self._kdrs_path = Path(selected)
            if self._reload():
                self.kdrs_label.setText("a11 KDRS QA: " + selected)
                self._settings.setValue("qt/a13_qa_path", selected)
            else:
                # Failed preflight leaves the prior snapshot and source selection intact.
                self._kdrs_path = previous

    def _choose_destination(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Velg overordnet katalog for ny a13-rapportmappe",
            str(self._settings.value("qt/a13_export_parent", "") or Path.home()))
        if directory:
            self._settings.setValue("qt/a13_export_parent", directory)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = str(self._row.job_id).replace("-", "_")
            self.out.setText(str(Path(directory) / f"noark5_a13_{name}_{stamp}"))

    def _generate(self):
        if self._worker is not None:
            return
        if self._dirty:
            QMessageBox.information(self, "Ulagret kommentar",
                                    "Lagre merknaden før eksport, eller oppdater funn for å forkaste endringen.")
            return
        if not self.out.text().strip():
            QMessageBox.information(self, "Rapport", "Velg en ny rapportmappe først.")
            return
        # Fetch API jobs on the GUI thread. The worker accesses only frozen
        # Python values and performs no Qt operations.
        report_api = self._panel._center._report_api
        jobs = ()
        if report_api is not None:
            try:
                jobs = tuple(report_api.selected_report_jobs((self._row.job_id,)))
            except (ValueError, OSError, AttributeError) as exc:
                QMessageBox.warning(self, "Rapport", "Kan ikke velge eksisterende a20-jobb: " + str(exc))
                return
        if not jobs:
            answer = QMessageBox.question(
                self, "a20-rapport mangler",
                "Finner ikke a20-jobb i aktiv jobbliste. Lage bare KS- og depotutkast, "
                "uten eksisterende Full-rapport og vedlegg A-D?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        out = Path(self.out.text().strip())
        work, depot_path, qa = self._work, self._depot_path, self._kdrs_path
        formats = ("html", "json", "csv", "pdf") if self.pdf.isChecked() else ("html", "json", "csv")
        self._worker = Thread(target=self._run_export, args=(work, out, depot_path, qa, jobs, formats),
                              daemon=True, name="dwm-a13-review-export")
        self.generate.setEnabled(False)
        self.save.setEnabled(False)
        self.close_button.setEnabled(False)
        self.message.setText("Bygger rapportpakke fra eksisterende DWM-resultater …")
        self._worker.start()
        self._timer.start()

    def _run_export(self, work, out, depot_path, qa, jobs, formats):
        try:
            result = export_review_bundle(work=work, output_dir=out, report_jobs=jobs,
                                          depot_report=depot_path, kdrs_qa=qa,
                                          a20_formats=formats)
            self._events.put(("done", str(result["index"])))
        except Exception as exc:
            self._events.put(("error", str(exc)))

    def _poll(self):
        try:
            kind, payload = self._events.get_nowait()
        except Empty:
            return
        self._timer.stop()
        self._worker = None
        self.generate.setEnabled(True)
        self.save.setEnabled(True)
        self.close_button.setEnabled(True)
        if kind == "done":
            self._last_export = Path(payload)
            self.open_last.setEnabled(True)
            self.message.setText("Rapportpakken er laget: " + payload)
            self._open_last()
        else:
            self.message.setText("Rapporteksport feilet: " + payload)
            QMessageBox.warning(self, "Rapporteksport", payload)

    def _open_last(self):
        if self._last_export is not None and self._last_export.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_export)))

    def reject(self):
        if self._worker is not None:
            QMessageBox.information(self, "Pågående rapporteksport", "Rapporteksporten må fullføres før vinduet kan lukkes.")
            return
        if self._uncommitted():
            return
        self._dirty = False
        super().reject()

    def closeEvent(self, event):
        if self._worker is not None or self._uncommitted():
            event.ignore()
        else:
            event.accept()


def install_qa_review_panel(viewer) -> None:
    """Add one launcher to the existing Depotvurdering tab; no duplicate page."""
    panel = getattr(viewer, "_a2_panel", None)
    if panel is None or getattr(panel, "_a13_qa_button", None) is not None:
        return
    button = QPushButton("KS / depot: vurder funn og lag rapporter…", panel)
    button.setToolTip("Registrer kildebundne faglige merknader; eksporter KS/depot-utkast og eksisterende a20 Full-rapport")

    def launch():
        row = panel.current_row()
        if row is None or row.report_path is None:
            QMessageBox.information(panel, "KS og depot", "Velg et uttrekk eller en arkivdel med original depotrapport.")
            return
        try:
            dialog = QaFindingReviewDialog(panel, row, parent=viewer)
        except (OSError, ValueError, ReportInputError) as exc:
            QMessageBox.warning(panel, "KS og depot", str(exc))
            return
        dialog.exec()

    button.clicked.connect(launch)
    panel.layout().addWidget(button)
    panel._a13_qa_button = button
    button.setEnabled(bool(panel.current_row() and panel.current_row().report_path))
    panel.tree.itemSelectionChanged.connect(
        lambda: button.setEnabled(bool(panel.current_row() and panel.current_row().report_path)))
