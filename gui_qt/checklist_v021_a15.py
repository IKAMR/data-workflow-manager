"""a15 Qt adapter for the *existing* Depotvurdering panel.

This is a manual checklist workbench, not a new report engine, legal ruleset,
or an automated depot approval. Original Work/Noark/Arkade evidence is read-only.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy,
    QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from noark5_workflow.reporting.qa_decision_v021_a12 import build_snapshot, ReportInputError
from noark5_workflow.reporting.qa_context_v021_a14 import enrich_snapshot
from noark5_workflow.reporting.qa_checklist_v021_a15 import (
    ChecklistError, DOC_MET, DOC_BASE, HEADER_FIELDS, GROUPS, POINTS,
    STATUSES, latest_checklist, mets_header, record_checklist,
)


class DepotChecklistDialog(QDialog):
    """One extracted Work and one exact scope, with no implicit J/N decisions."""

    def __init__(self, panel, row, parent=None):
        super().__init__(parent)
        self._panel = panel
        self._row = row
        self._work = Path(str((row.details or {}).get("work_root") or ""))
        if not self._work.is_dir() or not (self._work / "job.json").is_file():
            raise ChecklistError("Valgt uttrekk mangler gyldig DWM Work-jobb")
        if not row.report_path or not row.report_path.is_file():
            raise ChecklistError("Valgt uttrekk mangler original depotrapport")
        self._depot_rel = row.report_path.relative_to(self._work).as_posix()
        self._scope = row.scope
        self._native_id = row.native_id if row.scope == "arkivdel" else ""
        if self._scope == "arkivdel" and not self._native_id:
            raise ChecklistError("Arkivdel krever system-ID for kildebundet vurdering")
        self._snapshot = None
        self._current = {}
        self._selected_index = -1
        self._loading = False
        self._dirty = False
        target = row.title if self._scope == "arkivdel" else row.job_name
        self.setWindowTitle("Depotets sjekkliste – " + row.job_id + " – " + str(target))
        self.resize(1120, 790)
        self.setMinimumSize(850, 610)
        layout = QVBoxLayout(self)
        note = QLabel(
            "Depotets felles sjekkliste. Opplysningene fra Work/METS "
            "er dokumentasjon, ikke automatisk beståtte kontrollpunkter. "
            "Sjekkpunktene vurderes manuelt og er ikke depotvedtak."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs, 1)
        control_page = QWidget(self)
        control_layout = QVBoxLayout(control_page)
        selectors = QHBoxLayout()
        selectors.addWidget(QLabel("Område:"))
        self.section = QComboBox(self)
        self.section.addItem("Alle", "")
        for key, heading, _ref, _points in GROUPS:
            self.section.addItem(heading, key)
        self.section.addItem("Faglige tekstfelter / Noark 5", "notat")
        self.section.currentIndexChanged.connect(self._apply_filter)
        selectors.addWidget(self.section)
        selectors.addWidget(QLabel("Søk:"))
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Kontrollpunkt, referanse, tekstfelt")
        self.search.textChanged.connect(self._apply_filter)
        selectors.addWidget(self.search, 1)
        refresh = QPushButton("Oppdater sjekkliste", self)
        refresh.clicked.connect(self._reload)
        selectors.addWidget(refresh)
        control_layout.addLayout(selectors)
        self.summary = QLabel("Ingen kontrollpunkt er automatisk godkjent.")
        self.summary.setWordWrap(True)
        control_layout.addWidget(self.summary)
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.table = QTableWidget(len(POINTS), 4, self)
        self.table.setHorizontalHeaderLabels(("Område", "Sjekkpunkt / tekstfelt", "Svar", "Merknad"))
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col, width in ((0, 165), (2, 125), (3, 190)):
            self.table.setColumnWidth(col, width)
        self.table.itemSelectionChanged.connect(self._select)
        splitter.addWidget(self.table)
        editor = QWidget(self)
        e = QVBoxLayout(editor)
        self.point_label = QLabel("Velg et sjekkpunkt for faglig vurdering.")
        self.point_label.setWordWrap(True)
        e.addWidget(self.point_label)
        fields = QHBoxLayout()
        fields.addWidget(QLabel("Svar:"))
        self.status = QComboBox(self)
        self.status.currentIndexChanged.connect(self._mark_dirty)
        fields.addWidget(self.status, 1)
        self.ks = QCheckBox("Ta med i KS-rapport", self)
        self.ks.toggled.connect(self._mark_dirty)
        fields.addWidget(self.ks)
        self.depot = QCheckBox("Ta med i depotrapport", self)
        self.depot.setChecked(True)
        self.depot.toggled.connect(self._mark_dirty)
        fields.addWidget(self.depot)
        e.addLayout(fields)
        e.addWidget(QLabel("Merknad / begrunnelse (kreves ved Nei, Ikke relevant og fritekst):"))
        self.comment = QPlainTextEdit(self)
        self.comment.setPlaceholderText("Faglig begrunnelse, kilde eller oppfølging. Ikke endre originalverdier.")
        self.comment.setMinimumHeight(95)
        self.comment.textChanged.connect(self._mark_dirty)
        e.addWidget(self.comment, 1)
        buttons = QHBoxLayout()
        self.save = QPushButton("Lagre sjekkpunktvurdering", self)
        self.save.clicked.connect(self._save)
        buttons.addWidget(self.save)
        buttons.addStretch(1)
        e.addLayout(buttons)
        splitter.addWidget(editor)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([450, 320])
        control_layout.addWidget(splitter, 1)
        self.tabs.addTab(control_page, "Kontrollpunkter")

        metadata_page = QWidget(self)
        metadata_layout = QVBoxLayout(metadata_page)
        source_note = QLabel(
            "METS/Work-opplysninger vises fra to adskilte kilder. "
            "'Bevart info.xml' leses kun fra verifisert Work-kopi; 'Work' kan inneholde "
            "etterfølgende endringer. Manglende felter blir ikke automatisk feil eller Ja."
        )
        source_note.setWordWrap(True)
        metadata_layout.addWidget(source_note)
        self.complete_metadata_button = QPushButton("Komplett DIAS/METS: sammenlign og rediger metadata…", self)
        self.complete_metadata_button.clicked.connect(self._open_complete_metadata)
        metadata_layout.addWidget(self.complete_metadata_button)
        self.meta = QTableWidget(0, 3, self)
        self.meta.setHorizontalHeaderLabels(("Opplysning", "Registrert i Work", "Bevart METS info.xml"))
        self.meta.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.meta.verticalHeader().setVisible(False)
        self.meta.setAlternatingRowColors(True)
        self.meta.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.meta.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.meta.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        metadata_layout.addWidget(self.meta, 1)
        self.meta_note = QLabel("")
        self.meta_note.setWordWrap(True)
        metadata_layout.addWidget(self.meta_note)
        templates = QHBoxLayout()
        # The older checklist stays as history in repository; it is NOT a
        # competing operational checklist. A18 will consolidate the documents.
        for label, relative in (("Åpne sjekklisteutkast (kilde)…", DOC_MET),):
            button = QPushButton(label, self)
            button.clicked.connect(lambda checked=False, rel=relative: self._open_template(rel))
            templates.addWidget(button)
        templates.addStretch(1)
        metadata_layout.addLayout(templates)
        self.tabs.addTab(metadata_page, "Metadata og kilder")

        footer = QHBoxLayout()
        self.feedback = QLabel("")
        self.feedback.setWordWrap(True)
        footer.addWidget(self.feedback, 1)
        close = QPushButton("Lukk", self)
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        layout.addLayout(footer)
        self._reload()

    def _mark_dirty(self, *_args):
        if not self._loading:
            self._dirty = True

    def _confirm_discard(self):
        if not self._dirty:
            return True
        return QMessageBox.question(
            self, "Ulagret sjekkpunkt", "Forkast ulagret vurdering?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def _reload(self):
        if not self._confirm_discard():
            return
        try:
            snapshot = enrich_snapshot(self._work, build_snapshot(
                work=self._work, depot_report=self._depot_rel))
            result = latest_checklist(self._work, snapshot, scope=self._scope,
                                      native_id=self._native_id)
            header = mets_header(self._work, snapshot)
        except (OSError, ValueError, ReportInputError, ChecklistError) as exc:
            QMessageBox.warning(self, "Sjekkliste", str(exc))
            return
        self._snapshot = snapshot
        self._current = result["current"]
        self._dirty = False
        self._selected_index = -1  # ensure form reload even if same table row is selected
        self._render_table()
        self._render_metadata(header)
        self._select()
        self.feedback.setText(
            "Sjekklistegrunnlag lastet. " + str(result["older_or_changed"]) +
            " eldre vurderingshendelser gjelder ikke denne depotrapportversjonen."
        )

    def _render_table(self):
        self.table.blockSignals(True)
        for i, point in enumerate(POINTS):
            saved = self._current.get(point["id"])
            status = (STATUSES.get(saved["status"], "Faglig notat") if saved else "Ikke vurdert")
            values = (point["section_title"], point["label"], status,
                      "Merknad" if saved and saved["comment"] else "")
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(point["source_ref"] + " – " + point["label"])
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, i)
                self.table.setItem(i, col, item)
        self.table.blockSignals(False)
        controls = sum(p["kind"] == "control" for p in POINTS)
        reviewed = sum(p["kind"] == "control" and p["id"] in self._current for p in POINTS)
        scope = "hele uttrekket" if self._scope == "uttrekk" else "arkivdel " + self._native_id
        self.summary.setText(
            f"{scope}: {reviewed} av {controls} kontrollpunkter vurdert; "
            f"{len(self._current)} registreringer inkludert fritekst. "
            "Dette er manuelle vurderinger, ikke automatisk godkjenning."
        )
        self._apply_filter()
        if self._selected_index < 0 and POINTS:
            self.table.selectRow(0)
        elif 0 <= self._selected_index < len(POINTS):
            self.table.selectRow(self._selected_index)

    def _render_metadata(self, header):
        self.meta.setRowCount(len(header["rows"]))
        conflicts = 0
        for i, row in enumerate(header["rows"]):
            conflicts += int(row["conflict"])
            for col, value in enumerate((row["label"], row["work_value"] or "Ikke dokumentert",
                                         row["original_value"] or "Ikke dokumentert")):
                cell = QTableWidgetItem(str(value))
                if row["conflict"]:
                    cell.setToolTip("Ulike opplysninger i Work og bevart METS – krever menneskelig avstemming")
                    if col == 1:  # highlight only current changed/contradictory value
                        from PySide6.QtGui import QFont
                        font = QFont(cell.font())
                        font.setBold(True)
                        cell.setFont(font)
                self.meta.setItem(i, col, cell)
        orig = header.get("preserved_source")
        self.meta_note.setText(
            ("Bevart METS: " + orig["path"] + " · SHA-256 verifisert. " if orig else
             "Ingen verifiserbar bevart METS-kopi tilgjengelig. ") +
            (f"{conflicts} felt med ulike kildedata; de er ikke slått sammen." if conflicts else
             "METS-kilder er skilt fra registrerte Work-opplysninger.")
        )

    def _apply_filter(self, *_args):
        section = str(self.section.currentData() or "")
        needle = self.search.text().strip().casefold()
        for i, point in enumerate(POINTS):
            searchable = " ".join((point["label"], point["section_title"], point["source_ref"])).casefold()
            self.table.setRowHidden(i, bool(section and point["section"] != section or needle and needle not in searchable))

    def _select(self):
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            return
        index = selection[0].row()
        if index == self._selected_index and not self._dirty:
            return
        if index != self._selected_index and not self._confirm_discard():
            self.table.blockSignals(True)
            if self._selected_index >= 0:
                self.table.selectRow(self._selected_index)
            self.table.blockSignals(False)
            return
        self._selected_index = index
        self._dirty = False
        point = POINTS[index]
        saved = self._current.get(point["id"])
        self.point_label.setText(point["label"] + "  (" + point["source_ref"] + ")")
        self._loading = True
        try:
            self.status.clear()
            if point["kind"] == "note":
                self.status.addItem("Faglig tekstfelt", "note")
                self.status.setEnabled(False)
            else:
                self.status.addItem("Ikke vurdert", "")
                for key, text in STATUSES.items():
                    self.status.addItem(text, key)
                self.status.setEnabled(True)
                self.status.setCurrentIndex(self.status.findData(saved["status"]) if saved else 0)
            self.ks.setChecked(saved["include_in_ks"] if saved else False)
            self.depot.setChecked(saved["include_in_depot"] if saved else True)
            self.comment.setPlainText(saved["comment"] if saved else "")
        finally:
            self._loading = False
            self._dirty = False

    def _save(self):
        if self._selected_index < 0 or self._snapshot is None:
            QMessageBox.information(self, "Sjekkliste", "Velg et sjekkpunkt først.")
            return
        user = self._panel._identity()  # same identity policy as Depotvurdering/a13
        if user is None:
            return
        point = POINTS[self._selected_index]
        try:
            event = record_checklist(
                self._work, self._snapshot, point["id"],
                scope=self._scope, native_id=self._native_id,
                status=str(self.status.currentData() or ""),
                comment=self.comment.toPlainText(), user=user,
                include_in_ks=self.ks.isChecked(), include_in_depot=self.depot.isChecked(),
            )
            self._current[point["id"]] = event
            self._dirty = False
            self._render_table()
            self.feedback.setText("Lagret sjekklistevurdering (ikke depotvedtak): " + event["event_id"])
        except (OSError, ValueError, ReportInputError, ChecklistError) as exc:
            QMessageBox.warning(self, "Kan ikke lagre sjekkpunkt", str(exc))

    def _open_complete_metadata(self):
        if not self._confirm_discard():
            return
        try:
            from gui_qt.dias_metadata_v021_a16 import CompleteDiasMetadataDialog
            dialog = CompleteDiasMetadataDialog(self._work, self._panel, self)
        except (OSError, ValueError, ChecklistError) as exc:
            QMessageBox.warning(self, "Komplett DIAS/METS-metadata", str(exc))
            return
        dialog.exec()
        self._reload()  # reflect changes to the same canonical Work fields

    def _open_template(self, relative):
        root = Path(__file__).resolve().parents[1]
        path = root / relative
        if not path.is_file():
            QMessageBox.information(self, "Kildedokument", "Finnes ikke i denne installasjonen: " + relative)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def reject(self):
        if not self._confirm_discard():
            return
        self._dirty = False
        super().reject()

    def closeEvent(self, event):
        if not self._confirm_discard():
            event.ignore()
            return
        self._dirty = False
        event.accept()


def install_depot_checklist(viewer):
    """Attach to the existing Depotvurdering tab. No duplicate result center."""
    panel = getattr(viewer, "_a2_panel", None)
    if panel is None or getattr(panel, "_a15_checklist_button", None) is not None:
        return
    bar = QHBoxLayout()
    button = QPushButton("Sjekkliste / METS…", panel)
    button.setToolTip("Manuell J/N/ikke relevant-vurdering, kildebundet til Work; ingen automatisk depotgodkjenning")

    def launch():
        row = panel.current_row()
        if row is None or not row.report_path or not row.editable:
            QMessageBox.information(panel, "Depotets sjekkliste",
                                    "Velg uttrekk eller arkivdel med originalrapport og entydig system-ID.")
            return
        try:
            dialog = DepotChecklistDialog(panel, row, parent=viewer)
        except (OSError, ValueError, ReportInputError, ChecklistError) as exc:
            QMessageBox.warning(panel, "Depotets sjekkliste", str(exc))
            return
        dialog.exec()
        panel._center.refresh()

    button.clicked.connect(launch)
    bar.addWidget(button)
    bar.addStretch(1)
    # Reuse the a13 action row rather than adding another tall, full-width
    # button below an already crowded Depotvurdering panel.
    outer = panel.layout()
    qa = getattr(panel, "_a13_qa_button", None)
    index = outer.indexOf(qa) if qa is not None else -1
    if index >= 0:
        outer.removeWidget(qa)
        qa.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        bar.insertWidget(0, qa)
        outer.insertLayout(index, bar)
    else:
        outer.addLayout(bar)
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    panel._a15_checklist_button = button
    button.setEnabled(bool(panel.current_row() and panel.current_row().editable))
    panel.tree.itemSelectionChanged.connect(
        lambda: button.setEnabled(bool(panel.current_row() and panel.current_row().editable)))
