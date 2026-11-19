"""v0.2.3-a3: observed whole-extraction values and source-bound periods.

Extends a2 inspector without replacing the existing Noark/Arkade engines,
KS review ledger, source references, or XML value/standard-value crosswalk.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.ks_metadata_v023_a2 import catalogue_ids, field_rows, inspection_note
from app.ks_value_inspection_v023_a3 import (
    count_actual_xml_values, delivery_condition, delivery_relation,
    load_period_evidence, period_review_text, value_review_text,
)
from gui_qt.ks_metadata_v023_a2 import (
    OccurrenceInspectDialog as _A2OccurrenceInspectDialog,
    KsWorkshopDialog as _A2KsWorkshopDialog,
)


class _ValueCountWorker(QThread):
    complete = Signal(dict)
    failed = Signal(str)

    def __init__(self, work, bundle, version, metadata_id, archive_part_id='', parent=None):
        super().__init__(parent)
        self.work, self.bundle, self.version = work, bundle, version
        self.metadata_id, self.archive_part_id = metadata_id, archive_part_id

    def run(self):
        try:
            data = count_actual_xml_values(self.work, self.bundle, self.version,
                                           self.metadata_id, archive_part_id=self.archive_part_id,
                                           cancel=self.isInterruptionRequested)
        except (OSError, RuntimeError, ValueError, ImportError) as exc:
            self.failed.emit(str(exc))
        else:
            self.complete.emit(data)


class _PeriodEvidenceWorker(QThread):
    complete = Signal(dict)
    failed = Signal(str)

    def __init__(self, work, snapshot, parent=None):
        super().__init__(parent)
        self.work, self.snapshot = work, snapshot

    def run(self):
        try:
            data = load_period_evidence(self.work, self.snapshot)
        except (OSError, RuntimeError, ValueError) as exc:
            self.failed.emit(str(exc))
        else:
            self.complete.emit(data)


class OccurrenceInspectDialog(_A2OccurrenceInspectDialog):
    """Explicit read-only source census, and separate period-source assessment."""

    def __init__(self, *args, **kwargs):
        self._a3_count_worker = None
        self._a3_period_worker = None
        self._a3_period = None
        self._a3_counts = None
        # a1 constructor accepts (work, pinned_snapshot, ...).
        self._a3_snapshot = args[1] if len(args) > 1 else kwargs['snapshot']
        super().__init__(*args, **kwargs)
        self._a3_period_worker = _PeriodEvidenceWorker(self.work, self.data_snapshot, self)
        self._a3_period_worker.complete.connect(self._a3_period_ready)
        self._a3_period_worker.failed.connect(self._a3_period_failed)
        self._a3_period_worker.start()

    def _build_ui(self):
        super()._build_ui()
        # The a1 base retains its selected bound snapshot indirectly; store it
        # explicitly without touching its established source/evidence handling.
        # __init__ of the parent assigns data, rows and work beforehand.
        values_page = QWidget(self.detail_tabs)
        values_layout = QVBoxLayout(values_page)
        info = QLabel(
            'To forskjellige spørsmål: (1) Hvilke verdier er registrert i Noark-kodeverket? '
            '(2) Hvilke verdier forekommer faktisk i HELE arkivstruktur.xml? '
            'Den siste opptellingen startes bare når du trykker knappen. '
            'En kodeverdi som finnes i standarden kan fortsatt være et avleveringsavvik.')
        info.setWordWrap(True)
        values_layout.addWidget(info)
        row = QHBoxLayout()
        row.addWidget(QLabel('M-felt:'))
        self.a3_value_field = QComboBox(values_page)
        self.a3_value_field.setObjectName('v023_a3_value_field')
        self.a3_value_field.addItem('Venter på M-feltregister…', '')
        self.a3_value_field.currentIndexChanged.connect(self._a3_value_field_changed)
        row.addWidget(self.a3_value_field, 2)
        self.a3_count_button = QPushButton('Tell faktiske verdier i uttrekket', values_page)
        self.a3_count_button.setObjectName('v023_a3_count_actual_values')
        self.a3_count_button.setEnabled(False)
        self.a3_count_button.clicked.connect(self._a3_start_count)
        row.addWidget(self.a3_count_button)
        values_layout.addLayout(row)
        self.a3_value_status = QLabel('Opptelling er ikke startet. XML leses kun fra jobbens Source.')
        self.a3_value_status.setWordWrap(True)
        values_layout.addWidget(self.a3_value_status)
        self.a3_values_tree = QTreeWidget(values_page)
        self.a3_values_tree.setObjectName('v023_a3_standard_vs_observed')
        self.a3_values_tree.setHeaderLabels((
            'Feltverdi', 'Registrert standardverdi', 'Avlevering (kilde: v5.0)',
            'Forekomster i hele uttrekket', 'I valgt arkivdel'))
        self.a3_values_tree.setRootIsDecorated(False)
        self.a3_values_tree.setAlternatingRowColors(True)
        self.a3_values_tree.setUniformRowHeights(True)
        for col, width in enumerate((300, 230, 370, 225, 150)):
            self.a3_values_tree.setColumnWidth(col, width)
        values_layout.addWidget(self.a3_values_tree, 1)
        bottom = QLabel(
            'Opptelling = XML-feltforekomster i nåværende Source, ikke antall unike saker '
            'eller automatisk godkjenning. «Innenfor kodeverk» er adskilt fra Arkades '
            'vurdering av status ved avlevering. Ingen nye tester utføres.')
        bottom.setWordWrap(True)
        values_layout.addWidget(bottom)
        self.detail_tabs.addTab(values_page, 'Standardverdier og uttrekksverdier')

        period_page = QWidget(self.detail_tabs)
        period_layout = QVBoxLayout(period_page)
        label = QLabel(
            'Periodegrunnlag fra samme Work: jobbens LABEL, bevart ytre info.xml, '
            'lagret indre arkivuttrekk.xml / perioderapport og arkivdelens opplysninger. '
            'Disse er separate kilder og må ikke automatisk likestilles.')
        label.setWordWrap(True)
        period_layout.addWidget(label)
        self.a3_period_detail = QPlainTextEdit(period_page)
        self.a3_period_detail.setObjectName('v023_a3_period_sources')
        self.a3_period_detail.setReadOnly(True)
        self.a3_period_detail.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.a3_period_detail.setPlainText('Leser periodegrunnlag fra jobbens lagrede Work…')
        period_layout.addWidget(self.a3_period_detail)
        self.detail_tabs.addTab(period_page, 'Perioder og kilder')

        self.metadata_lookup.currentIndexChanged.connect(self._a3_lookup_selected)
        self.metadata_tree.currentItemChanged.connect(self._a3_metadata_selected)

    @property
    def data_snapshot(self):
        # a1's first constructor argument is the pinned KS snapshot; a2 calls
        # super() unchanged. It is persisted by __init__ in this class via the
        # constructor wrapper below, not recomputed from any unrelated job.
        return self._a3_snapshot

    def _a3_refill_field_choice(self):
        if not self._bundle:
            return
        version = str(self.metadata_version.currentData() or '5.0')
        current_id = str(self.a3_value_field.currentData() or '')
        self.a3_value_field.blockSignals(True)
        self.a3_value_field.clear()
        self.a3_value_field.addItem('Velg M-felt…', '')
        for mid, name in catalogue_ids(self._bundle, version):
            self.a3_value_field.addItem(mid + ' · ' + name, mid)
        # Automatically highlight the actually inspected object's selected XML
        # field, not an unrelated guessed M number.
        xml_name = str(self._xml_metadata.get('element') or '')
        matching = [r['metadata_id'] for r in field_rows(self._xml_metadata, self._bundle, version)
                    if r.get('xml_field') == xml_name and r.get('is_selected') and r.get('metadata_id')]
        wanted = current_id if self.a3_value_field.findData(current_id) >= 0 and current_id else (
            matching[0] if len(matching) == 1 else '')
        self.a3_value_field.setCurrentIndex(max(0, self.a3_value_field.findData(wanted)))
        self.a3_value_field.blockSignals(False)
        self.a3_count_button.setEnabled(bool(wanted) and self._a3_count_worker is None)

    def _reference_completed(self, bundle: dict):
        super()._reference_completed(bundle)
        self._a3_refill_field_choice()

    def _reference_failed(self, message: str):
        super()._reference_failed(message)
        self.a3_count_button.setEnabled(False)
        self.a3_value_status.setText('Opptelling krever M-feltregisteret: ' + message)

    def _reader_completed(self, result: dict):
        super()._reader_completed(result)
        self._a3_counts = None
        self.a3_values_tree.clear()
        self.a3_value_status.setText('Velg M-felt og start opptelling av faktiske verdier i hele uttrekket.')
        self._a3_refill_field_choice()
        self._a3_show_period()

    def _selected(self, current, previous):
        super()._selected(current, previous)
        self._a3_counts = None
        if hasattr(self, 'a3_values_tree'):
            self.a3_values_tree.clear()
            self.a3_value_status.setText('Ny forekomst valgt. Tidligere telledata er fjernet fra visningen.')
        if hasattr(self, 'a3_period_detail'):
            self._a3_show_period()

    def _metadata_version_changed(self, *_):
        super()._metadata_version_changed(*_)
        self._a3_counts = None
        if hasattr(self, 'a3_values_tree'):
            self.a3_values_tree.clear()
            self.a3_value_status.setText('Referanseversjon endret. Tell på nytt for oppdatert kodeverkssammenligning.')
            self._a3_refill_field_choice()

    def _a3_value_field_changed(self, *_):
        self._a3_counts = None
        self.a3_values_tree.clear()
        self.a3_count_button.setEnabled(bool(self.a3_value_field.currentData())
                                        and self._bundle is not None and self._a3_count_worker is None)
        self.a3_value_status.setText('Velg «Tell faktiske verdier i uttrekket» for dette M-feltet.')

    def _a3_metadata_selected(self, item, _previous):
        if item is None or not self._bundle:
            return
        mid = str(item.data(0, Qt.ItemDataRole.UserRole) or '')
        i = self.a3_value_field.findData(mid)
        if mid and i >= 0:
            self.a3_value_field.setCurrentIndex(i)

    def _a3_lookup_selected(self, *_):
        mid = str(self.metadata_lookup.currentData() or '')
        i = self.a3_value_field.findData(mid)
        if mid and i >= 0:
            self.a3_value_field.setCurrentIndex(i)

    def _a3_start_count(self):
        if self._a3_count_worker is not None or not self._bundle:
            return
        if getattr(self, '_reader', None) is not None:
            QMessageBox.information(self, 'Verdier i uttrekk',
                                    'Avslutt pågående XML-forekomstlesing før full opptelling.')
            return
        mid = str(self.a3_value_field.currentData() or '')
        if not mid:
            QMessageBox.information(self, 'Verdier i uttrekk', 'Velg et registrert M-felt først.')
            return
        version = str(self.metadata_version.currentData() or '5.0')
        item = self.tree.currentItem()
        i = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        part_id = self.rows[i].get('archive_part_id', '') if type(i) is int and 0 <= i < len(self.rows) else ''
        self._a3_counts = None
        self.a3_values_tree.clear()
        self.a3_count_button.setEnabled(False)
        self.a3_value_field.setEnabled(False)
        self.metadata_version.setEnabled(False)
        self.metadata_lookup.setEnabled(False)
        self.metadata_tree.setEnabled(False)
        self.tree.setEnabled(False)
        self.a3_value_status.setText('Teller faktisk forekommende XML-verdier i Source… '
                                      'Ingen filer endres og ingen tester kjøres.')
        self._a3_count_worker = _ValueCountWorker(self.work, self._bundle, version, mid, part_id, self)
        self._a3_count_worker.complete.connect(self._a3_count_ready)
        self._a3_count_worker.failed.connect(self._a3_count_failed)
        self._a3_count_worker.finished.connect(self._a3_count_finished)
        self._a3_count_worker.start()

    def _a3_count_ready(self, counts: dict):
        # Never turn errors or partial reads into reassuring zero counts.
        self._a3_counts = counts if counts.get('complete') else None
        self.a3_values_tree.clear()
        for row in counts.get('values') or ():
            scope = row.get('archive_part')
            item = QTreeWidgetItem((str(row['value']) or '(tom verdi)',
                                    str(row['reference_relation']),
                                    str(row['delivery_relation']),
                                    str(row['total']),
                                    '—' if scope is None else str(scope)))
            self.a3_values_tree.addTopLevelItem(item)
        if counts.get('outside_registered_set') is None:
            in_set = 'intet registrert verdisett'
        else:
            in_set = (f"{counts['inside_registered_set']} i registrert verdisett; "
                      f"{counts['outside_registered_set']} utenfor")
        cond = counts.get('delivery_condition')
        delivery_summary = (
            f" Kildebundet avleveringsbetingelse: {counts['eligible_at_delivery']} innenfor, "
            f"{counts['not_eligible_at_delivery']} utenfor. "
            f"{cond['source_title']} s. {cond['page']}.") if cond else (
                ' Ingen dokumentert avleveringsklassifisering for denne referanseversjonen/feltet.')
        self.a3_value_status.setText(
            f"FERDIG – {counts['metadata_id']} / {counts['xml_field']}: "
            f"{counts['observed_total']} feltforekomster, {counts['observed_distinct']} ulike verdier; "
            + in_set + '.' + delivery_summary + ' Kilde: ' + counts['source_path'] + '. '
            + counts['provenance_note'])

    def _a3_count_failed(self, error: str):
        self._a3_counts = None
        self.a3_values_tree.clear()
        self.a3_value_status.setText('Opptellingen ble IKKE fullført. Ingen delresultater vises. ' + error)

    def _a3_count_finished(self):
        self._a3_count_worker = None
        self.a3_value_field.setEnabled(True)
        self.metadata_version.setEnabled(True)
        self.metadata_lookup.setEnabled(True)
        self.metadata_tree.setEnabled(True)
        self.tree.setEnabled(self._reader is None)
        self.a3_count_button.setEnabled(bool(self.a3_value_field.currentData()) and self._bundle is not None)

    def _a3_period_ready(self, info: dict):
        self._a3_period = info
        self._a3_show_period()

    def _a3_period_failed(self, error: str):
        self._a3_period = None
        self.a3_period_detail.setPlainText('Periodegrunnlaget kunne ikke leses kildebundet: ' + error)

    def _a3_show_period(self):
        if not getattr(self, 'a3_period_detail', None):
            return
        if self._a3_period is None:
            self.a3_period_detail.setPlainText('Leser kildebundet perioderapport fra Work…')
            return
        item = self.tree.currentItem()
        i = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        part_id = self.rows[i].get('archive_part_id', '') if type(i) is int and 0 <= i < len(self.rows) else ''
        text = period_review_text(self._a3_period, self._xml_metadata, archive_part_id=part_id)
        self.a3_period_detail.setPlainText(text)

    def _show_detail(self, ident: str):
        super()._show_detail(ident)
        if not self._bundle:
            return
        version = str(self.metadata_version.currentData() or '5.0')
        try:
            condition = delivery_condition(self._bundle, version, ident)
        except (OSError, ValueError) as exc:
            self.metadata_detail.appendPlainText(
                '\nAVLEVERINGSBETINGELSE: Kildekontroll mislyktes: ' + str(exc))
            return
        if condition is None:
            self.metadata_detail.appendPlainText(
                '\nAVLEVERINGSBETINGELSE: Ikke registrert som kildeverifisert for '
                'dette M-feltet og denne referanseversjonen. Dette er IKKE en godkjenning.')
            return
        details = [
            'AVLEVERINGSBETINGELSE (SKILLE MELLOM STANDARDKODE OG AVLEVERINGSVILKÅR)',
            'Gjelder: ' + condition['applies_to'],
            'Verdier angitt som tillatt VED AVLEVERING: ' + ', '.join(condition['delivery_values']),
            'Kilde: ' + condition['source_title'] + ', s. ' + str(condition['page']),
            'Kildelenke: ' + condition['source_url'],
            'Dette er kun en kildebasert sammenligning; Arkade-testens resultat'
            ' og faglig depotbeslutning beholdes adskilt.',
        ]
        metadata = self._xml_metadata or {}
        if metadata.get('element') == condition['xml_field']:
            observed = str(metadata.get('xml_value') or '')
            details.extend(('Observert i VALGT objekt: ' + observed,
                            'Vurdering mot avleveringsbetingelsen: '
                            + delivery_relation(observed, condition)))
        self.metadata_detail.appendPlainText('\n\n' + '\n'.join(details))

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
        if self._a3_period:
            note += '\n\n' + period_review_text(
                self._a3_period, self._xml_metadata,
                archive_part_id=str(self._last_arkade_row.get('archive_part_id') or ''))
        if self._a3_counts:
            note += '\n\n' + value_review_text(self._a3_counts)
        # Ulagret kladd: a2 KsWorkshopDialog handles the editor; the existing
        # append-only Work review API remains the only way to persist it.
        self.review_evidence_note = note
        self.accept()

    def _close_reader(self):
        if self._a3_count_worker is not None and self._a3_count_worker.isRunning():
            self._a3_count_worker.requestInterruption()
            self._a3_count_worker.wait()
        if self._a3_period_worker is not None and self._a3_period_worker.isRunning():
            self._a3_period_worker.wait()
        super()._close_reader()


class KsWorkshopDialog(_A2KsWorkshopDialog):
    """Identical a2 work selection and append-only KS behavior; new inspect dialog."""

    def _show_inspector(self, finding: dict | None = None, test_id: str | None = None):
        try:
            dialog = OccurrenceInspectDialog(
                self.work, self.snapshot, finding=finding, test_id=test_id, parent=self)
            dialog.exec()
            if finding is not None and dialog.review_evidence_note:
                existing = self.review_comment.toPlainText().rstrip()
                comment = (existing + '\n\n' if existing else '') + dialog.review_evidence_note
                self.review_comment.setPlainText(comment)
                self.review_comment.setFocus()
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, 'Inspiser Arkade-funn', str(exc))
