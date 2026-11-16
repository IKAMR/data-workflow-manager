"""v0.2.1-a16 complete DIAS/METS source comparison and Work-side metadata editor."""
from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView,
)

from noark5_workflow.reporting.dias_metadata_v021_a16 import (
    MetadataA16Error, import_inner_mets, load_metadata, save_field,
)

MAX_VISIBLE = 450  # Search/filter spans all indexed records; draw only 450 at once.


class CompleteDiasMetadataDialog(QDialog):
    def __init__(self, work: Path, panel, parent=None):
        super().__init__(parent)
        self.work = Path(work)
        self.panel = panel
        self.context: dict = {}
        self.row_lookup: list[dict] = []
        self.selected_id = ""
        self.loading = False
        self.dirty = False
        self.setWindowTitle("Komplett DIAS/METS-metadata – original og gjeldende")
        self.resize(1470, 870)
        self.setMinimumSize(1010, 625)
        body = QVBoxLayout(self)
        top = QLabel("47 Arkade-metadatafelt er hovedoversikten, med kildehenvisning i begge METS-formatene "
                     "per felt. Supplerende METS-opplysninger og komplett teknisk XML vises hver for seg. "
                     "Endringer lagres bare i Work; originalfiler og sjekksummer endres aldri.")
        top.setWordWrap(True)
        body.addWidget(top)

        source_bar = QHBoxLayout()
        source_bar.addWidget(QLabel("Bevart kilde:"))
        self.source_box = QComboBox(self)
        self.source_box.currentIndexChanged.connect(self._change_source)
        source_bar.addWidget(self.source_box, 1)
        import_button = QPushButton("Importer METS-kopi til Work…", self)
        import_button.clicked.connect(self._import_source)
        source_bar.addWidget(import_button)
        refresh = QPushButton("Oppdater", self)
        refresh.clicked.connect(self._reload)
        source_bar.addWidget(refresh)
        body.addLayout(source_bar)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Vis:"))
        self.section = QComboBox(self)
        self.section.addItem("Metadata – 47 Arkade-felt", "canonical")
        self.section.addItem("Depotopplysninger – 4 felt", "depot")
        self.section.addItem("Utvidede METS-opplysninger", "extended")
        self.section.addItem("Teknisk XML – alle forekomster", "xml")
        self.section.addItem("Bare ulike / endrede", "changed")
        self.section.currentIndexChanged.connect(self._filter)
        filters.addWidget(self.section)
        filters.addWidget(QLabel("Søk:"))
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Felt, kategori, XML-sti eller verdi")
        self.search.textChanged.connect(self._filter)
        filters.addWidget(self.search, 1)
        body.addLayout(filters)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(("Kategori / metadatafelt", "Importert / historisk", "Gjeldende i Work",
                                              "Sammenligning", "Ytre info.xml", "Indre DIAS METS"))
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        # Fixed useful initial proportions + interactive resizing/horizontal scroll
        # prevent field names from being squeezed by two evidence-reference columns.
        for column, width in enumerate((255, 190, 190, 130, 300, 300)):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(column, width)
        self.table.itemSelectionChanged.connect(self._selected)
        body.addWidget(self.table, 1)

        editor = QWidget(self)
        edit_layout = QGridLayout(editor)
        self.selected_label = QLabel("Velg et felt for å se originale METS-referanser og eventuelt redigere Work.")
        self.selected_label.setWordWrap(True)
        edit_layout.addWidget(self.selected_label, 0, 0, 1, 2)
        self.references = QPlainTextEdit(self)
        self.references.setReadOnly(True)
        self.references.setMaximumHeight(84)
        self.references.setPlaceholderText("Kildereferanser for ytre info.xml og indre dias-mets.xml")
        edit_layout.addWidget(self.references, 1, 0, 1, 2)
        edit_layout.addWidget(QLabel("Bevart kildeverdi (skrivebeskyttet):"), 2, 0)
        edit_layout.addWidget(QLabel("Gjeldende verdi (endring lagres i Work):"), 2, 1)
        self.original = QPlainTextEdit(self)
        self.original.setReadOnly(True)
        self.original.setMaximumHeight(92)
        edit_layout.addWidget(self.original, 3, 0)
        self.current = QPlainTextEdit(self)
        self.current.setMaximumHeight(92)
        self.current.textChanged.connect(self._changed)
        edit_layout.addWidget(self.current, 3, 1)
        edit_layout.addWidget(QLabel("Begrunnelse for endringen:"), 4, 0)
        self.reason = QLineEdit(self)
        self.reason.setPlaceholderText("Faglig begrunnelse / avklaring – obligatorisk")
        self.reason.textChanged.connect(self._changed)
        edit_layout.addWidget(self.reason, 4, 1)
        action_bar = QHBoxLayout()
        self.save_button = QPushButton("Lagre endring i Work", self)
        self.save_button.clicked.connect(self._save)
        self.save_button.setEnabled(False)
        action_bar.addWidget(self.save_button)
        action_bar.addStretch(1)
        self.feedback = QLabel("")
        self.feedback.setWordWrap(True)
        action_bar.addWidget(self.feedback)
        edit_layout.addLayout(action_bar, 5, 0, 1, 2)
        body.addWidget(editor)
        close_bar = QHBoxLayout()
        close_bar.addStretch(1)
        close = QPushButton("Lukk", self)
        close.clicked.connect(self.reject)
        close_bar.addWidget(close)
        body.addLayout(close_bar)
        self._reload()

    def _dirty_confirmation(self) -> bool:
        if not self.dirty:
            return True
        return QMessageBox.question(
            self, "Ulagret metadata", "Forkast ulagret metadataendring?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def _change_source(self, *_args):
        if self.loading:
            return
        if not self._dirty_confirmation():
            self.loading = True
            previous = self.context.get("selected_source") or {}
            index = self.source_box.findData(previous.get("sha256"))
            self.source_box.setCurrentIndex(index if index >= 0 else 0)
            self.loading = False
            return
        self._reload()

    def _reload(self):
        if not self._dirty_confirmation():
            return
        self.dirty = False
        source_sha = self.source_box.currentData() if self.source_box.count() else None
        try:
            data = load_metadata(self.work, source_sha)
        except (OSError, ValueError, MetadataA16Error) as exc:
            QMessageBox.warning(self, "Kan ikke lese METS-metadata", str(exc))
            return
        self.context = data
        self.loading = True
        try:
            self.source_box.blockSignals(True)
            self.source_box.clear()
            if not data["sources"]:
                self.source_box.addItem("Ingen bevart kilde – vis gjeldende Work-felt", None)
            for source in data["sources"]:
                self.source_box.addItem(
                    str(source.get("original_name") or Path(source["path"]).name) +
                    " · " + source["sha256"][:10], source["sha256"])
            chosen = data.get("selected_source")
            self.source_box.setCurrentIndex(max(0, self.source_box.findData(
                chosen["sha256"] if chosen else None)))
            self.source_box.blockSignals(False)
            self.selected_id = ""
            self.dirty = False
            self.reason.clear()
            self.feedback.setText("")
            self._filter()
        finally:
            self.loading = False

    @staticmethod
    def _reference_short(info: dict | None) -> str:
        if not info:
            return "–"
        if info["status"] == "ikke kartlagt":
            return "Ikke kartlagt"
        ref = str(info.get("expected") or "")
        # A brief path inside the row; the precise expected/observed path,
        # source filename, SHA-256 and stored value are shown below/tooltip.
        if "altRecordID[" in ref:
            match = re.search(r"altRecordID\[@TYPE='([^']+)'\]", ref)
            ref = "altRecordID / " + (match.group(1) if match else "ukjent type")
        elif "agent[" in ref:
            other = re.search(r"@OTHERROLE='([^']+)'", ref)
            role = re.search(r"@ROLE='([^']+)'", ref)
            typ = re.search(r"@TYPE='([^']+)'", ref)
            note = re.search(r"notescontent:([A-Za-z]+)", ref)
            suffix = note.group(1) if note else ("name" if ref.endswith(":name") else "")
            ref = " / ".join(x for x in (
                other.group(1) if other else role.group(1) if role else "agent",
                "SOFTWARE" if "@OTHERTYPE='SOFTWARE'" in ref else typ.group(1) if typ else "",
                suffix,
            ) if x)
        else:
            ref = ref.rsplit("/", 1)[-1]
        state = {"påvist": "Påvist", "ikke påvist": "Ikke påvist",
                 "kilde ikke importert": "Kilde ikke importert"}.get(info["status"], info["status"])
        return ref + " · " + state

    @staticmethod
    def _reference_details(info: dict, label: str) -> str:
        status = info["status"]
        lines = [label + ": " + status]
        if info.get("source_name"):
            lines.append("  Kilde: " + str(info["source_name"]))
        if info.get("sha256"):
            lines.append("  SHA-256: " + str(info["sha256"]))
        if info.get("expected"):
            lines.append("  Feltplassering: " + str(info["expected"]))
        if info.get("actual"):
            lines.append("  Faktisk XML-forekomst: " + str(info["actual"]))
            lines.append("  Originalverdi: " + str(info["value"] if info["value"] is not None else ""))
        if info.get("note"):
            lines.append("  Merknad: " + str(info["note"]))
        return "\n".join(lines)

    def _filter(self, *_args):
        mode = str(self.section.currentData() or "canonical")
        needle = self.search.text().strip().casefold()
        all_rows = self.context.get("rows") or []
        if mode == "extended":
            candidates = self.context.get("extended_rows") or []
        elif mode == "changed":
            candidates = ([r for r in all_rows if r["kind"] in ("canonical", "depot")]
                          + list(self.context.get("extended_rows") or []))
        elif mode == "xml":
            candidates = [r for r in all_rows if r["kind"] == "xml"]
        else:
            candidates = [r for r in all_rows if r["kind"] == mode]
        filtered = []
        for row in candidates:
            if mode == "changed" and not row["changed"]:
                continue
            values = [str(row.get(key) or "") for key in
                      ("group", "label", "key", "current", "historical", "status")]
            for ref in (row.get("references") or {}).values():
                values.extend(str(ref.get(k) or "") for k in
                              ("expected", "actual", "status", "source_name", "value"))
            if needle and not any(needle in value.casefold() for value in values):
                continue
            filtered.append(row)
        visible = filtered[:MAX_VISIBLE]
        self.row_lookup = visible
        show_refs = mode in ("canonical", "changed")
        self.table.blockSignals(True)
        self.table.setColumnHidden(4, not show_refs)
        self.table.setColumnHidden(5, not show_refs)
        self.table.setRowCount(len(visible))
        palette = self.table.palette()
        dark = palette.color(QPalette.ColorRole.Base).lightness() < 130
        changed_color = QColor("#ffd58a" if dark else "#794200")
        for index, row in enumerate(visible):
            group = row["group"] + " · " + row["label"]
            source = row["historical"] if row["historical"] is not None else "Ikke oppgitt i kilden"
            current = row["current"] if row["current"] else "Ikke utfylt i Work"
            refs = row.get("references") or {}
            vals = (group, source, current, row["status"].capitalize(),
                    self._reference_short(refs.get("outer")),
                    self._reference_short(refs.get("inner")))
            for col, val in enumerate(vals):
                cell = QTableWidgetItem(str(val))
                tooltip = row["key"] + "\n" + str(val)
                if col in (4, 5) and refs:
                    role = "outer" if col == 4 else "inner"
                    if role in refs:
                        tooltip = self._reference_details(
                            refs[role], "Ytre info.xml" if col == 4 else "Indre dias-mets.xml")
                cell.setToolTip(tooltip)
                if row.get("source_conflict") and col in (4, 5):
                    font = QFont(cell.font())
                    font.setBold(True)
                    cell.setFont(font)
                    cell.setForeground(changed_color)
                    cell.setToolTip(tooltip + "\nYtre og indre kildeverdier er ulike – må avstemmes faglig.")
                if row["changed"] and col in (2, 3):
                    font = QFont(cell.font())
                    font.setBold(True)
                    cell.setFont(font)
                    cell.setForeground(changed_color)
                self.table.setItem(index, col, cell)
        self.table.blockSignals(False)
        modes = {
            "canonical": "Arkade 5-metadata (uten rå XML-duplikater)",
            "depot": "Separate depotopplysninger – ikke METS",
            "extended": "Tillegg fra den valgte METS-kilden, gruppert uten duplikater",
            "xml": "Teknisk, fullstendig XML-inventar – bare for kildeinnsyn",
            "changed": "Ulike/endrede arbeidsverdier – uten dupliserte XML-felt",
        }
        pair = self.context.get("paired_sources") or {}
        paired = ("Ytre info.xml: " + ("importert" if "outer" in pair else "ikke importert") +
                  " · Indre dias-mets.xml: " + ("importert" if "inner" in pair else "ikke importert"))
        paired_diff = int(self.context.get("paired_differences") or 0)
        if paired_diff:
            paired += f" · {paired_diff} felt med ulike kildeverdier (ikke automatisk feil)"
        self.status.setText(
            modes.get(mode, "Metadata") + " · " +
            f"{len(visible)} av {len(filtered)} treff. " + paired + ". " +
            ("Original SHA-256 kontrollert." if self.context.get("source_original_preserved") else
             "Ingen verifiserbar bevart kilde valgt.")
        )
        if visible:
            self.table.selectRow(0)
        else:
            self.selected_id = ""
            self._display_selection(None)

    def _selected(self):
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            return
        row = self.row_lookup[selection[0].row()]
        if row["id"] != self.selected_id and not self._dirty_confirmation():
            self.table.blockSignals(True)
            old_index = next((i for i, item in enumerate(self.row_lookup)
                              if item["id"] == self.selected_id), None)
            if old_index is not None:
                self.table.selectRow(old_index)
            self.table.blockSignals(False)
            return
        self.selected_id = row["id"]
        self._display_selection(row)

    def _display_selection(self, row):
        self.loading = True
        try:
            self.dirty = False
            self.save_button.setEnabled(bool(row and row["editable"]))
            self.original.setPlainText("" if row is None or row["historical"] is None else row["historical"])
            self.current.setPlainText("" if row is None else row["current"])
            self.current.setReadOnly(not row or not row["editable"])
            self.reason.clear()
            self.selected_label.setText(
                (row["group"] + " · " + row["label"] + "\n" + row["key"] if row else
                 "Velg et metadatafelt. Endringer av gjeldende verdier krever begrunnelse."))
            refs = row.get("references") if row else None
            if refs:
                self.references.setPlainText(
                    self._reference_details(refs["outer"], "Ytre info.xml") + "\n\n" +
                    self._reference_details(refs["inner"], "Indre dias-mets.xml"))
            elif row and row.get("kind") in ("xml", "summary"):
                self.references.setPlainText(
                    "Teknisk kildeinnsyn – valgt bevart METS-kilde: " +
                    str((self.context.get("selected_source") or {}).get("original_name") or "") +
                    "\nFull XML-sti: " + row["key"] +
                    "\nOriginalfilen er skrivebeskyttet. "
                    "Tekniske identiteter/sjekksummer kan ikke redigeres.")
            elif row and row.get("kind") == "depot":
                self.references.setPlainText(
                    "Depotets eget katalog-/arbeidsfelt. "
                    "Dette feltet har ingen mapping til ytre info.xml eller indre DIAS METS.")
            else:
                self.references.clear()
        finally:
            self.loading = False

    def _changed(self, *_args):
        if self.loading:
            return
        self.dirty = True

    def _import_source(self):
        if not self._dirty_confirmation():
            return
        self.dirty = False
        path, _ = QFileDialog.getOpenFileName(self, "Velg ytre info.xml eller indre dias-mets.xml", "",
                                               "METS XML (*.xml);;Alle filer (*)")
        if not path:
            return
        try:
            source = import_inner_mets(self.work, path)
        except (OSError, ValueError, MetadataA16Error) as exc:
            QMessageBox.warning(self, "Kunne ikke bevare METS-kilde", str(exc))
            return
        self._reload()
        index = self.source_box.findData(source["sha256"])
        if index >= 0:
            self.source_box.setCurrentIndex(index)
        self.feedback.setText("Kildekopi bevart i Work med SHA-256: " + source["sha256"][:20])

    def _save(self):
        row = next((r for r in self.context.get("rows") or [] if r["id"] == self.selected_id), None)
        if not row or not row["editable"]:
            return
        user = self.panel._identity()  # reuse the same DWM user identity as a13/a15
        if user is None:
            return
        author = user.as_dict()
        if row["kind"] == "xml" and "fileSec" in row["key"]:
            warning = QMessageBox.question(
                self, "Tekniske filmetadata",
                "Dette er en merknad/arbeidsverdi i Work. Verken filens innhold, "
                "METS-originalen eller sjekksummer blir endret. Registrere arbeidsverdien?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if warning != QMessageBox.StandardButton.Yes:
                return
        try:
            save_field(
                self.work, source_sha256=(self.context.get("selected_source") or {}).get("sha256"),
                row_id=row["id"], previous_value=row["current"],
                new_value=self.current.toPlainText(), comment=self.reason.text(),
                author=author, expected_metadata_sha256=self.context.get("metadata_sha256"),
            )
        except (OSError, ValueError, MetadataA16Error) as exc:
            QMessageBox.warning(self, "Metadata ikke lagret", str(exc))
            return
        self.dirty = False
        self._reload()
        self.feedback.setText("Endring registrert i Work. Den originale XML-filen er uendret.")

    def reject(self):
        if self._dirty_confirmation():
            self.dirty = False
            super().reject()

    def closeEvent(self, event):
        if not self._dirty_confirmation():
            event.ignore()
        else:
            self.dirty = False
            event.accept()
