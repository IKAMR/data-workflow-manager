"""v0.2.3-a2: versioned metadata/value/XPath inspection inside Basic KS.

Reuses a1's selected, verified Arkade evidence and read-only XML inspection,
plus the existing Advanced-mode versioned metadata and XPath crosswalk.
The separate reference worker never scans Source or starts DWM tests.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.ks_metadata_v023_a2 import (
    VERSIONS, catalogue_ids, field_detail, field_rows, load_reference_bundle, inspection_note,
)
from gui_qt.ks_inspector_v023_a1 import (
    OccurrenceInspectDialog as _A1OccurrenceInspectDialog,
    KsWorkshopDialog as _A1KsWorkshopDialog,
)


class _MetadataReferenceWorker(QThread):
    completed = Signal(dict)
    failed = Signal(str)

    def run(self):
        try:
            result = load_reference_bundle()
        except (ImportError, OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(result)


class OccurrenceInspectDialog(_A1OccurrenceInspectDialog):
    """Inspect actual XML values, registered M fields and candidate XPath links."""

    def __init__(self, *args, **kwargs):
        self._xml_metadata = {}
        self._bundle = None
        self._metadata_worker = None
        self._last_xml_result = None
        self._last_arkade_row = None
        self.review_evidence_note = ''
        self._allow_comment_handoff = kwargs.get('finding') is not None
        super().__init__(*args, **kwargs)
        self._start_reference_worker()

    def _build_ui(self):
        super()._build_ui()
        parent = self.detail.parentWidget()
        layout = parent.layout()
        layout.removeWidget(self.detail)
        self.detail_tabs = QTabWidget(parent)
        self.detail_tabs.setObjectName('v023_a2_xml_and_metadata_tabs')
        self.detail_tabs.addTab(self.detail, 'XML-kontekst')
        page = QWidget(self.detail_tabs)
        outer = QVBoxLayout(page)
        info = QLabel(
            'M-numre og standardverdier hentes fra samme registrerte Noark-kilder og '
            'XPath-/KDRS-koblinger som i Avansert modus. Velg referanseversjon: '
            'dette fastslår ikke uttrekkets faktiske Noark-versjon. '
            'En tillatt kode kan fortsatt være et avleveringsavvik.')
        info.setWordWrap(True)
        outer.addWidget(info)
        selector = QHBoxLayout()
        selector.addWidget(QLabel('Referanseversjon:'))
        self.metadata_version = QComboBox(page)
        for version in VERSIONS:
            self.metadata_version.addItem('Noark 5 v' + version + ' (valgt referanse)', version)
        self.metadata_version.setCurrentIndex(self.metadata_version.findData('5.0'))
        self.metadata_version.currentIndexChanged.connect(self._metadata_version_changed)
        selector.addWidget(self.metadata_version)
        selector.addWidget(QLabel('M-feltoppslag:'))
        self.metadata_lookup = QComboBox(page)
        self.metadata_lookup.setMinimumWidth(225)
        self.metadata_lookup.addItem('Venter på metadataregister…', '')
        self.metadata_lookup.currentIndexChanged.connect(self._metadata_lookup_changed)
        selector.addWidget(self.metadata_lookup, 1)
        outer.addLayout(selector)
        self.metadata_note = QLabel('Leser versjonert metadata-/XPath-register…')
        self.metadata_note.setWordWrap(True)
        outer.addWidget(self.metadata_note)
        self.metadata_splitter = QSplitter(Qt.Orientation.Vertical, page)
        self.metadata_splitter.setChildrenCollapsible(False)
        self.metadata_tree = QTreeWidget(self.metadata_splitter)
        self.metadata_tree.setHeaderLabels((
            'M-felt', 'XML-felt', 'Observert verdi i objektet', 'Verdisett / kilde'))
        self.metadata_tree.setRootIsDecorated(False)
        self.metadata_tree.setAlternatingRowColors(True)
        self.metadata_tree.setUniformRowHeights(True)
        for col, width in enumerate((80, 180, 320, 315)):
            self.metadata_tree.setColumnWidth(col, width)
        self.metadata_tree.header().setStretchLastSection(False)
        self.metadata_tree.currentItemChanged.connect(self._metadata_field_selected)
        self.metadata_detail = QPlainTextEdit(self.metadata_splitter)
        self.metadata_detail.setReadOnly(True)
        self.metadata_detail.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.metadata_detail.setPlainText(
            'Velg først «Vis XML-kontekst for valgt forekomst». '\
            'Registrerte M-felt og standardverdier kan også slås opp uten et XML-treff.')
        self.metadata_splitter.setSizes([180, 330])
        outer.addWidget(self.metadata_splitter, 1)
        self.detail_tabs.addTab(page, 'M-felt, verdier og XPath')
        layout.addWidget(self.detail_tabs)
        # No automatic review writes: this is an explicit draft hand-off only.
        self.add_review_note = QPushButton('Bruk inspisert kildehenvisning i KS-kommentar')
        self.add_review_note.setEnabled(False)
        self.add_review_note.setToolTip(
            'Legger dokumentert Arkade-/XML-referanse inn i kommentarfeltet som et utkast; '
            'brukeren må lagre den faglige vurderingen selv.')
        actions = self.layout().itemAt(self.layout().count() - 1).layout()
        actions.insertWidget(0, self.add_review_note)
        self.add_review_note.clicked.connect(self._handoff_to_review)
        if not self._allow_comment_handoff:
            self.add_review_note.hide()

    def _start_reference_worker(self):
        self._metadata_worker = _MetadataReferenceWorker(self)
        self._metadata_worker.completed.connect(self._reference_completed)
        self._metadata_worker.failed.connect(self._reference_failed)
        self._metadata_worker.start()

    def _reference_completed(self, bundle: dict):
        self._bundle = bundle
        self._update_metadata_views()
        if hasattr(self, 'add_review_note'):
            self.add_review_note.setEnabled(bool(self._allow_comment_handoff and self._last_xml_result
                                                 and self._last_arkade_row))

    def _reference_failed(self, message: str):
        self.metadata_note.setText(
            'Metadata-/XPath-registeret kunne ikke leses. Eksisterende XML- og '
            'Arkade-evidens er fremdeles tilgjengelig. ' + message)
        self.metadata_detail.setPlainText('Ingen normativ feltkobling kan utledes uten de registrerte kildene.')

    def _selected(self, current, previous):
        # a1 populates Arkade-provenance and resets the XML excerpt.
        self._xml_metadata = {}
        self._last_xml_result = None
        self._last_arkade_row = None
        if hasattr(self, 'add_review_note'):
            self.add_review_note.setEnabled(False)
        super()._selected(current, previous)
        if hasattr(self, 'metadata_tree'):
            self._update_metadata_views()

    def _reader_completed(self, result: dict):
        super()._reader_completed(result)
        self._xml_metadata = dict(result.get('metadata') or {}) if result.get('available') else {}
        self._last_xml_result = result if result.get('available') else None
        item = self.tree.currentItem()
        i = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if (type(i) is int and 0 <= i < len(self.rows)
                and self.rows[i]['line'] == result.get('line') and result.get('available')):
            self._last_arkade_row = self.rows[i]
        else:
            self._last_arkade_row = None
        if hasattr(self, 'add_review_note'):
            self.add_review_note.setEnabled(bool(self._allow_comment_handoff and self._bundle
                                                 and self._last_xml_result and self._last_arkade_row))
        self._update_metadata_views()

    def _metadata_version_changed(self, *_):
        self._update_metadata_views()

    def _metadata_lookup_changed(self, *_):
        self._show_selected_catalogue()

    def _metadata_field_selected(self, item, _previous):
        if item is None:
            return
        ident = str(item.data(0, Qt.ItemDataRole.UserRole) or '')
        if not ident:
            self.metadata_detail.setPlainText(
                'Dette observerte XML-feltnavnet er ikke registrert som et '
                'entydig M-felt i valgt versjonskatalog. Ingen M-nummer er antatt.')
            return
        if self._bundle:
            self._show_detail(ident)

    def _show_selected_catalogue(self):
        if self._bundle is None:
            return
        ident = str(self.metadata_lookup.currentData() or '')
        if ident:
            self._show_detail(ident)

    def _show_detail(self, ident: str):
        if not self._bundle:
            return
        version = str(self.metadata_version.currentData() or '5.0')
        try:
            self.metadata_detail.setPlainText(field_detail(
                self._xml_metadata, self._bundle, version, ident))
        except ValueError as exc:
            self.metadata_detail.setPlainText('Ingen verifiserbar metadataregistrering: ' + str(exc))

    def _update_metadata_views(self):
        if not hasattr(self, 'metadata_tree'):
            return
        version = str(self.metadata_version.currentData() or '5.0')
        self.metadata_tree.blockSignals(True)
        self.metadata_lookup.blockSignals(True)
        prior = str(self.metadata_lookup.currentData() or '')
        self.metadata_tree.clear()
        self.metadata_lookup.clear()
        try:
            if not self._bundle:
                self.metadata_lookup.addItem('Venter på metadataregister…', '')
                self.metadata_note.setText('Leser versjonerte Noark-/XPath-kilder i bakgrunnen…')
                return
            ids = catalogue_ids(self._bundle, version)
            self.metadata_lookup.addItem('Velg M-felt for separat oppslag…', '')
            for ident, name in ids:
                self.metadata_lookup.addItem(ident + ' · ' + name, ident)
            rows = field_rows(self._xml_metadata, self._bundle, version)
            for row in rows:
                item = QTreeWidgetItem((row['metadata_id'] or '—', row['xml_field'],
                                        row['value'], row['value_relation']))
                item.setData(0, Qt.ItemDataRole.UserRole, row['metadata_id'])
                item.setToolTip(2, row['xpath'])
                self.metadata_tree.addTopLevelItem(item)
                if row.get('is_selected') and row['metadata_id']:
                    self.metadata_tree.setCurrentItem(item)
            state = self._bundle['versions'].get(version, {}).get('state', 'unavailable')
            coverage = str(self._xml_metadata.get('field_coverage') or 'ingen XML-kontekst')
            self.metadata_note.setText(
                f'Noark 5 v{version} er valgt som referanse – ikke verifisert som uttrekkets '
                f'Noark-versjon. Register: {state}. Direkte objektfelt: {len(rows)}. '
                f'XML-dekning: {coverage}.')
            if prior and self.metadata_lookup.findData(prior) >= 0:
                self.metadata_lookup.setCurrentIndex(self.metadata_lookup.findData(prior))
            if self.metadata_tree.currentItem() is None and not prior:
                self.metadata_detail.setPlainText(
                    'Ingen observerte XML-felt med entydig M-kobling i valgt objekt. '
                    'Bruk M-feltoppslaget over for M300, M082, M500, M502 osv.')
            elif self.metadata_tree.currentItem() is not None:
                self._metadata_field_selected(self.metadata_tree.currentItem(), None)
            if prior and self.metadata_lookup.currentData() == prior:
                self._show_detail(prior)
        finally:
            self.metadata_tree.blockSignals(False)
            self.metadata_lookup.blockSignals(False)

    def _handoff_to_review(self):
        if not self._bundle or not self._last_xml_result or not self._last_arkade_row:
            QMessageBox.information(self, 'KS-kommentar', 'Inspiser konkret XML-forekomst først.')
            return
        version = str(self.metadata_version.currentData() or '5.0')
        try:
            note = inspection_note(self._last_arkade_row, self._last_xml_result,
                                   self._bundle, version)
        except ValueError as exc:
            QMessageBox.warning(self, 'KS-kommentar', str(exc))
            return
        self.review_evidence_note = note
        self.accept()

    def _close_reader(self):
        if self._metadata_worker is not None and self._metadata_worker.isRunning():
            self._metadata_worker.wait()
        super()._close_reader()


class KsWorkshopDialog(_A1KsWorkshopDialog):
    """Keep the existing a1 inspection buttons and all a12 KS/review behavior."""

    def _show_inspector(self, finding: dict | None = None, test_id: str | None = None):
        try:
            dialog = OccurrenceInspectDialog(
                self.work, self.snapshot, finding=finding, test_id=test_id, parent=self)
            dialog.exec()
            if finding is not None and dialog.review_evidence_note:
                # Explicit operator choice; modifies only the UNSAVED editor.
                # The existing a12 Work review API handles any eventual save.
                existing = self.review_comment.toPlainText().rstrip()
                comment = (existing + '\n\n' if existing else '') + dialog.review_evidence_note
                self.review_comment.setPlainText(comment)
                self.review_comment.setFocus()
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, 'Inspiser Arkade-funn', str(exc))
