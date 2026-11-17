"""DWM v0.2.2-a3: direct review, manual findings, KS and depot draft reports.

Reuses the existing a13 dialog and original Resultatvisninger/depot review
panel. No new Qt startup hooks, popup filters or timers are installed.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QTableWidgetItem, QWidget,
)

from gui_qt.qa_review_v021_a13 import QaFindingReviewDialog as _ExistingDialog
from noark5_workflow.reporting.qa_review_v021_a13 import (
    STATUSES, finding_key, latest_reviews, ReviewError,
)
from noark5_workflow.reporting.qa_workflow_v022_a3 import (
    SEVERITIES, build_review_snapshot_v022_a3, ensure_qa_evidence_parent,
    finding_summary, record_manual_finding,
)
from noark5_workflow.reporting.qa_export_v022_a3 import export_review_bundle_v022_a3


class QaFindingReviewDialogV022A3(_ExistingDialog):
    """Expanded a13 GUI: no new evidence store or report rendering engine."""

    def __init__(self, panel, row, parent=None):
        super().__init__(panel, row, parent=parent)
        self.setWindowTitle("Avvik, kvalitetssikring og godkjenning – " + row.job_id)
        self.generate.setText("Lag KS- og godkjenningsutkast + Full-rapport")
        self.generate.setToolTip("Lager egne utkast til arkivskaper og depot, med avviksregister. Ingen automatisk godkjenning.")
        self.register_manual = QPushButton("+ Registrer manuelt avvik / observasjon", self)
        self.register_manual.setToolTip("Et dokumentert menneskelig funn; ikke en ny maskinell test.")
        self.register_manual.clicked.connect(self._add_manual_finding)
        self.only_open = QCheckBox("Vis bare funn uten faglig vurdering", self)
        self.only_open.toggled.connect(self._filter)
        self.progress = QLabel(self)
        self.progress.setWordWrap(True)
        line = QWidget(self)
        toolbar = QHBoxLayout(line)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addWidget(self.register_manual)
        toolbar.addWidget(self.only_open)
        toolbar.addStretch(1)
        # Keep the original a13 layout and worker logic; do not touch window
        # geometry or global Qt event filters after the a2 stability fixes.
        self.layout().insertWidget(2, line)
        self.layout().insertWidget(3, self.progress)
        self._refresh_progress()

    def _reload(self):
        """Load the same canonical sources plus append-only manual findings."""
        if self._uncommitted():
            return False
        try:
            candidate = build_review_snapshot_v022_a3(
                work=self._work, depot_report=self._depot_path,
                kdrs_qa=self._kdrs_path)
            findings = list(candidate["findings"])
            current = latest_reviews(self._work, candidate)["current"]
        except (ValueError, OSError, TypeError, KeyError) as error:
            QMessageBox.warning(self, "Kontrollgrunnlag", str(error))
            return False
        self._snapshot = candidate
        self._findings = findings
        self._current_reviews = current
        self._active_key = None
        self._dirty = False
        self.table.blockSignals(True)
        self.table.setRowCount(len(findings))
        for row, item in enumerate(findings):
            key = finding_key(item)
            event = current.get(key)
            values = (
                item["severity"], item["test_id"], item["source"], item["message"],
                STATUSES.get(event["status"], event["status"]) if event else "Ikke vurdert",
            )
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setToolTip(str(value))
                if col == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, row)
                self.table.setItem(row, col, cell)
        self.table.blockSignals(False)
        self._filter()
        if findings:
            self.table.selectRow(0)
            self._choose_finding()
        else:
            self.explanation.setPlainText("Ingen registrerte kildefunn. Dette er ikke en godkjenning.")
        self._refresh_progress()
        self.message.setText(
            f"{len(findings)} kildefunn · {len(current)} faglig vurdert. "
            "Originale testresultater og eventuelle manuelle observasjoner endres ikke."
        )
        return True

    def _filter(self, *_args):
        super()._filter(*_args)
        only_open = bool(getattr(self, "only_open", None) and self.only_open.isChecked())
        if not only_open:
            return
        for row, item in enumerate(self._findings):
            if finding_key(item) in self._current_reviews:
                self.table.setRowHidden(row, True)

    def _refresh_progress(self):
        if not hasattr(self, "progress") or not self._snapshot:
            return
        counts = finding_summary(self._work, self._snapshot)
        self.progress.setText(
            f"Avviksregister: {counts['total']} funn · {counts['unreviewed']} uten vurdering · "
            f"{counts['reviewed']} vurdert · {counts['errors']} tekniske feilfunn · "
            f"{counts['warnings']} advarsler · {counts['manual']} manuelle. "
            "Faglig vurdering er ikke depotgodkjenning."
        )

    def _save_review(self):
        # A completed ordinary DWM Work has no optional canonical/evidence
        # directory until a person explicitly saves a finding or review.
        try:
            ensure_qa_evidence_parent(self._work)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Work", str(error))
            return
        super()._save_review()
        self._refresh_progress()
        self._filter()

    def _add_manual_finding(self):
        if self._worker is not None or self._uncommitted():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Registrer manuelt avvik / observasjon")
        dialog.resize(710, 440)
        layout = QFormLayout(dialog)
        notice = QLabel(
            "Registreres kildebundet i valgt Work og tas med i avviksregisteret. "
            "Dette oppretter ingen automatisk Noark-test, endrer ingen testresultater "
            "og godkjenner ikke uttrekket.", dialog)
        notice.setWordWrap(True)
        layout.addRow(notice)
        severity = QComboBox(dialog)
        labels = {"ERROR": "Feil – manuelt observert", "WARNING": "Advarsel", "REVIEW": "Krever vurdering",
                  "NOTE": "Merknad", "INFORMATION": "Informasjon"}
        for code in SEVERITIES:
            severity.addItem(labels[code], code)
        severity.setCurrentIndex(severity.findData("REVIEW"))
        layout.addRow("Nivå:", severity)
        message = QPlainTextEdit(dialog)
        message.setPlaceholderText("Beskriv det konkrete avviket/observasjonen og hvorfor det skal følges opp")
        layout.addRow("Observasjon *:", message)
        context = QLineEdit(dialog)
        context.setPlaceholderText("Arkivdel / system-ID / berørt registrering (valgfritt)")
        layout.addRow("Kontekst:", context)
        source = QLineEdit(dialog)
        source.setPlaceholderText("Kildereferanse eller XML-fil (valgfritt; ingen filer endres)")
        layout.addRow("Kilde:", source)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Registrer funn")
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        def save():
            author = self._panel._identity()
            if author is None:
                return
            try:
                record_manual_finding(
                    self._work, self._snapshot, severity=severity.currentData(),
                    message=message.toPlainText(), context=context.text(),
                    file=source.text(), user=author)
            except (ValueError, OSError, TypeError, KeyError) as error:
                QMessageBox.warning(dialog, "Avvik", str(error))
                return
            dialog.accept()

        buttons.accepted.connect(save)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._reload()

    def _choose_destination(self):
        """Select existing parent, create a *new* named report folder on export."""
        base = str(self._settings.value("qt/a3_export_parent", "") or Path.home())
        directory = QFileDialog.getExistingDirectory(
            self, "Velg overordnet mappe for KS-/godkjenningsrapport", base)
        if directory:
            self._settings.setValue("qt/a3_export_parent", directory)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = str(self._row.job_id).replace("-", "_")
            self.out.setText(str(Path(directory) / f"noark5_a3_{name}_{stamp}"))

    def _run_export(self, work, out, depot_path, qa, jobs, formats):
        """Worker thread: frozen values only, no GUI calls."""
        try:
            result = export_review_bundle_v022_a3(
                work=work, output_dir=out, report_jobs=jobs,
                depot_report=depot_path, kdrs_qa=qa, a20_formats=formats)
            self._events.put(("done", str(result["index"])))
        except Exception as error:
            self._events.put(("error", str(error)))


def launch_review_for_panel(panel, viewer):
    row = panel.current_row()
    if row is None or row.report_path is None:
        QMessageBox.information(panel, "KS og depot", "Velg et uttrekk med en original depotrapport.")
        return
    try:
        dialog = QaFindingReviewDialogV022A3(panel, row, parent=viewer)
    except (OSError, ValueError, TypeError) as error:
        QMessageBox.warning(panel, "KS og depot", str(error))
        return
    dialog.exec()


def install_qa_review_panel(viewer) -> None:
    """One entry inside Faglig vurdering, replacing the hidden a13 launcher."""
    panel = getattr(viewer, "_a2_panel", None)
    if panel is None or getattr(panel, "_a13_qa_button", None) is not None:
        return
    button = QPushButton("Avvik / KS / godkjenning…", panel)
    button.setToolTip("Registrer alle kildefunn og manuelle observasjoner, og lag separate rapportutkast.")
    button.clicked.connect(lambda: launch_review_for_panel(panel, viewer))
    panel.layout().addWidget(button)
    panel._a13_qa_button = button

    def refresh():
        row = panel.current_row()
        button.setEnabled(bool(row is not None and row.report_path is not None))
    panel.tree.itemSelectionChanged.connect(refresh)
    refresh()


def open_active_job_qa(window) -> None:
    """Direct launcher from both Basic overview and Advanced Rapport menu."""
    job_id = getattr(window, "_active_id", None)
    if not job_id:
        QMessageBox.information(window, "Avvik og rapporter", "Velg en jobb først.")
        return
    # The canonical result/depot pane already resolves work + original report.
    before = tuple(getattr(window, "_a12_result_windows", ()))
    window._a12_open_result_center(depot=True)
    created = [viewer for viewer in getattr(window, "_a12_result_windows", ()) if viewer not in before]
    if not created:
        return
    viewer = created[-1]
    panel = getattr(viewer, "_a2_panel", None)
    if panel is None:
        QMessageBox.warning(window, "Avvik", "Depotvurdering er ikke tilgjengelig i resultatvinduet.")
        return
    viewer.show_depot_review()
    # Select *this* job explicitly. The Resultatvisninger window may offer
    # more than one job, and a generic 'content' name cannot identify it.
    for row in getattr(panel, "_rows", ()):
        if row.job_id == job_id and row.scope == "uttrekk":
            item = panel._items.get(row.key)
            if item is not None:
                panel.tree.setCurrentItem(item)
                break
    current = panel.current_row()
    if current is None or current.job_id != job_id or current.report_path is None:
        QMessageBox.information(window, "Avvik", "Ingen lagret depotrapport for aktiv jobb. Velg riktig uttrekk i Resultatvisninger.")
        return
    launch_review_for_panel(panel, viewer)
