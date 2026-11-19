"""v0.2.3-a4: one linear KS review per actual issue, in the existing dialog.

No new validator, duplicate review ledger or automatic decision.  Existing
Arkade SHA-256/line validation, on-demand XML reader, versioned M-field
catalogue and append-only review API are reused without modification.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.ks_guided_v023_a4 import (
    ordered_findings, find_index, inspect_relation, metadata_for_test,
    review_evidence_note,
)
from app.ks_inspector_v023_a1 import arkade_occurrences
from app.ks_metadata_v023_a2 import load_reference_bundle
from app.ks_value_inspection_v023_a3 import delivery_condition
from app.ks_workshop_v022_a12 import save_review, WorkshopError
from noark5_workflow.reporting.qa_review_v021_a13 import STATUSES
from gui_qt.ks_inspector_v023_a1 import _XmlReader
from gui_qt.ks_value_inspection_v023_a3 import KsWorkshopDialog as _A3KsDialog


class _CatalogueReader(QThread):
    complete = Signal(dict)
    failed = Signal(str)

    def run(self):
        try:
            self.complete.emit(load_reference_bundle())
        except (OSError, ValueError, RuntimeError, ImportError) as exc:
            self.failed.emit(str(exc))


class KsWorkshopDialog(_A3KsDialog):
    """Guided mode is default; the established analysis/report tabs remain."""

    def _build_ui(self):
        # The a12 constructor invokes this method and _reload virtually.
        self._guided_selected_key = ''
        self._guided_current = None
        self._guided_rows = ()
        self._guided_occurrences = None
        self._guided_anchor = None
        self._guided_xml = None
        self._guided_bundle = None
        self._guided_catalogue_worker = None
        self._guided_reader = None
        self._guided_dirty = False
        self._guided_loading = False
        self._guided_changing_tab = False
        super()._build_ui()
        guided = QWidget(self.tabs)
        self.guided_page = guided
        layout = QVBoxLayout(guided)
        header = QHBoxLayout()
        self.guided_progress = QLabel('KS-gjennomgang – velg avvik')
        self.guided_progress.setStyleSheet('font-weight:bold; font-size:14px')
        header.addWidget(self.guided_progress, 1)
        self.guided_scope = QComboBox(guided)
        self.guided_scope.addItem('Feil først', 'errors')
        self.guided_scope.addItem('Alle funn', 'all')
        self.guided_scope.currentIndexChanged.connect(self._guided_scope_changed)
        header.addWidget(self.guided_scope)
        self.guided_previous = QPushButton('← Forrige', guided)
        self.guided_previous.clicked.connect(lambda: self._guided_advance(-1))
        header.addWidget(self.guided_previous)
        self.guided_choice = QComboBox(guided)
        self.guided_choice.setObjectName('v023_a4_finding_selector')
        self.guided_choice.currentIndexChanged.connect(self._guided_choice_changed)
        header.addWidget(self.guided_choice, 2)
        self.guided_next = QPushButton('Neste →', guided)
        self.guided_next.clicked.connect(lambda: self._guided_advance(1))
        header.addWidget(self.guided_next)
        layout.addLayout(header)
        self.guided_issue = QLabel('Velg et avvik for kildebundet inspeksjon')
        self.guided_issue.setWordWrap(True)
        layout.addWidget(self.guided_issue)

        splitter = QSplitter(Qt.Orientation.Vertical, guided)
        splitter.setChildrenCollapsible(False)
        sources = QWidget(splitter)
        sl = QVBoxLayout(sources)
        sl.setContentsMargins(3, 3, 3, 3)
        sl.addWidget(QLabel('1. Kontroller dokumenterte treff i Arkade-evidensen'))
        self.guided_source = QLabel('Kildegrunnlag avventes')
        self.guided_source.setWordWrap(True)
        sl.addWidget(self.guided_source)
        self.guided_occurrences = QTreeWidget(sources)
        self.guided_occurrences.setObjectName('v023_a4_source_occurrences')
        self.guided_occurrences.setRootIsDecorated(False)
        self.guided_occurrences.setAlternatingRowColors(True)
        self.guided_occurrences.setUniformRowHeights(True)
        self.guided_occurrences.setHeaderLabels(['Nr.', 'Arkivdel', 'XML-fil', 'Linje', 'Objekt systemID'])
        for n, width in enumerate((50, 270, 165, 95, 235)):
            self.guided_occurrences.setColumnWidth(n, width)
        self.guided_occurrences.header().setStretchLastSection(True)
        self.guided_occurrences.currentItemChanged.connect(self._guided_occurrence_selected)
        self.guided_occurrences.itemDoubleClicked.connect(lambda *_: self._guided_inspect_xml())
        sl.addWidget(self.guided_occurrences, 1)
        row = QHBoxLayout()
        self.guided_open_xml = QPushButton('Vis XML for valgt objekt', sources)
        self.guided_open_xml.setObjectName('v023_a4_open_xml')
        self.guided_open_xml.clicked.connect(self._guided_inspect_xml)
        row.addWidget(self.guided_open_xml)
        self.guided_source_file = QPushButton('Åpne lagret Arkade-kilde', sources)
        self.guided_source_file.clicked.connect(self._guided_open_source_file)
        row.addWidget(self.guided_source_file)
        row.addStretch(1)
        sl.addLayout(row)
        sl.addWidget(QLabel('2. Funn → XML-felt → M-nummer → registrert verdi → avleveringsbetingelse'))
        self.guided_reference_version = QComboBox(sources)
        for v in ('5.0', '4.0', '3.1'):
            self.guided_reference_version.addItem('Noark 5 v' + v + ' (referanse)', v)
        self.guided_reference_version.currentIndexChanged.connect(self._guided_rule_text)
        sl.addWidget(self.guided_reference_version)
        self.guided_rule = QPlainTextEdit(sources)
        self.guided_rule.setObjectName('v023_a4_field_and_rule')
        self.guided_rule.setReadOnly(True)
        self.guided_rule.setMaximumHeight(115)
        sl.addWidget(self.guided_rule)
        self.guided_xml_view = QPlainTextEdit(sources)
        self.guided_xml_view.setObjectName('v023_a4_xml_context')
        self.guided_xml_view.setReadOnly(True)
        self.guided_xml_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        sl.addWidget(self.guided_xml_view, 1)
        splitter.addWidget(sources)

        review = QWidget(splitter)
        rl = QVBoxLayout(review)
        rl.setContentsMargins(3, 3, 3, 3)
        rl.addWidget(QLabel('3. Registrer faglig vurdering før du går videre'))
        statusrow = QHBoxLayout()
        statusrow.addWidget(QLabel('Faglig status:'))
        self.guided_review_status = QComboBox(review)
        self.guided_review_status.addItem('Ikke vurdert', '')
        for code, name in STATUSES.items():
            self.guided_review_status.addItem(name, code)
        self.guided_review_status.currentIndexChanged.connect(self._guided_mark_dirty)
        statusrow.addWidget(self.guided_review_status, 1)
        self.guided_in_ks = QCheckBox('Inkluder kommentar i KS-rapport', review)
        self.guided_in_ks.setChecked(True)
        self.guided_in_ks.toggled.connect(self._guided_mark_dirty)
        statusrow.addWidget(self.guided_in_ks)
        self.guided_in_depot = QCheckBox('Inkluder i depotrapport', review)
        self.guided_in_depot.setChecked(True)
        self.guided_in_depot.toggled.connect(self._guided_mark_dirty)
        statusrow.addWidget(self.guided_in_depot)
        rl.addLayout(statusrow)
        self.guided_comment = QPlainTextEdit(review)
        self.guided_comment.setObjectName('v023_a4_review_comment')
        self.guided_comment.setPlaceholderText('Forklar avviket, aktuelle objekter, uklarheter og avtalt oppfølging…')
        self.guided_comment.textChanged.connect(self._guided_mark_dirty)
        rl.addWidget(self.guided_comment, 1)
        actions = QHBoxLayout()
        self.guided_insert_source = QPushButton('Sett kildehenvisning inn i kommentar', review)
        self.guided_insert_source.clicked.connect(self._guided_add_source_note)
        actions.addWidget(self.guided_insert_source)
        actions.addStretch(1)
        self.guided_save = QPushButton('Lagre vurdering', review)
        self.guided_save.setObjectName('v023_a4_save_review')
        self.guided_save.clicked.connect(self._guided_save_review)
        actions.addWidget(self.guided_save)
        self.guided_save_next = QPushButton('Lagre og neste →', review)
        self.guided_save_next.setObjectName('v023_a4_save_and_next')
        self.guided_save_next.clicked.connect(lambda: self._guided_save_review(move_next=True))
        actions.addWidget(self.guided_save_next)
        rl.addLayout(actions)
        self.guided_save_note = QLabel('Lagres i eksisterende KS-register i Work, ikke i Source.')
        self.guided_save_note.setWordWrap(True)
        rl.addWidget(self.guided_save_note)
        splitter.addWidget(review)
        splitter.setSizes([510, 235])
        layout.addWidget(splitter, 1)

        self.tabs.insertTab(0, guided, 'Veiledet KS')
        self.tabs.setCurrentWidget(guided)
        self.tabs.currentChanged.connect(self._guided_tab_changed)
        self.guided_previous.setEnabled(False)
        self.guided_next.setEnabled(False)
        self.guided_open_xml.setEnabled(False)
        self.guided_insert_source.setEnabled(False)
        self.guided_save.setEnabled(False)
        self.guided_save_next.setEnabled(False)

    def _reload(self, *, select_key: str = ''):
        retain = select_key or getattr(self, '_guided_selected_key', '')
        super()._reload(select_key=select_key)
        if hasattr(self, 'guided_choice'):
            self._guided_refill(retain)
        if (getattr(self, '_guided_catalogue_worker', None) is None
                and self._guided_bundle is None and not getattr(self, '_guided_catalogue_failed', False)):
            self._guided_catalogue_worker = _CatalogueReader(self)
            self._guided_catalogue_worker.complete.connect(self._guided_catalogue_ready)
            self._guided_catalogue_worker.failed.connect(self._guided_catalogue_error)
            self._guided_catalogue_worker.start()

    def _guided_catalogue_ready(self, bundle):
        self._guided_bundle = bundle
        self._guided_rule_text()

    def _guided_catalogue_error(self, error):
        self._guided_catalogue_failed = True
        self.guided_rule.setPlainText('M-registeret kan ikke lastes: ' + error +
                                     '\nArkade-evidens og faglig kommentering er fortsatt tilgjengelige.')

    def _guided_refill(self, desired=''):
        rows = ordered_findings(self.all_findings,
                                errors_only=self.guided_scope.currentData() == 'errors')
        self._guided_rows = rows
        self._guided_loading = True
        self.guided_choice.blockSignals(True)
        self.guided_choice.clear()
        try:
            for i, row in enumerate(rows, 1):
                descr = str(row.get('message') or '')[:100]
                reviewed = '✓ ' if row.get('review_status') else ''
                self.guided_choice.addItem(
                    f'{reviewed}{i:02d}. {row.get("test_id") or "Funn"} – {descr}',
                    str(row.get('finding_key') or ''))
            n = find_index(rows, desired)
            self.guided_choice.setCurrentIndex(max(0, n))
        finally:
            self.guided_choice.blockSignals(False)
            self._guided_loading = False
        self._guided_select(self.guided_choice.currentData() or '')

    def _guided_scope_changed(self, *_):
        if self._guided_loading:
            return
        if not self._guided_can_leave():
            self.guided_scope.blockSignals(True)
            try:
                self.guided_scope.setCurrentIndex(0 if len(self._guided_rows) == sum(
                    str(r.get('severity') or '').upper() == 'ERROR' for r in self.all_findings) else 1)
            finally:
                self.guided_scope.blockSignals(False)
            return
        self._guided_refill(self._guided_selected_key)

    def _guided_choice_changed(self, *_):
        if self._guided_loading:
            return
        key = self.guided_choice.currentData() or ''
        if key == self._guided_selected_key:
            return
        if not self._guided_can_leave():
            self._guided_restore_selector()
            return
        self._guided_select(key)

    def _guided_restore_selector(self):
        self.guided_choice.blockSignals(True)
        try:
            self.guided_choice.setCurrentIndex(max(0, find_index(self._guided_rows, self._guided_selected_key)))
        finally:
            self.guided_choice.blockSignals(False)

    def _guided_advance(self, amount: int):
        idx = find_index(self._guided_rows, self._guided_selected_key)
        dest = idx + amount
        if not 0 <= dest < len(self._guided_rows) or self._guided_reader is not None:
            return
        self.guided_choice.setCurrentIndex(dest)  # guarded by _guided_choice_changed

    def _guided_select(self, key: str):
        self._guided_selected_key = str(key)
        row = next((r for r in self._guided_rows if r.get('finding_key') == key), None)
        self._guided_current = row
        self._guided_anchor = None
        self._guided_xml = None
        self._guided_occurrences = None
        self.guided_occurrences.clear()
        self.guided_xml_view.setPlainText('Velg en XML-linje og trykk «Vis XML for valgt objekt».')
        index = find_index(self._guided_rows, key)
        reviewed = sum(bool(r.get('review_status')) for r in self._guided_rows)
        self.guided_progress.setText(f'Funn {index + 1 if row else 0} av {len(self._guided_rows)} · {reviewed} vurdert')
        self.guided_previous.setEnabled(index > 0)
        self.guided_next.setEnabled(row is not None and index + 1 < len(self._guided_rows))
        self.guided_source_file.setEnabled(bool(row and row.get('source_ref')))
        self.guided_save.setEnabled(row is not None)
        self.guided_save_next.setEnabled(row is not None)
        self._guided_loading = True
        try:
            self.guided_review_status.setCurrentIndex(max(0, self.guided_review_status.findData(
                row.get('review_status') if row else '')))
            self.guided_comment.setPlainText(str(row.get('review_comment') or '') if row else '')
            self.guided_in_ks.setChecked(bool(row.get('include_in_ks', True)) if row else True)
            self.guided_in_depot.setChecked(bool(row.get('include_in_depot', True)) if row else True)
        finally:
            self._guided_loading = False
        self._guided_dirty = False
        self.guided_save_note.setText('Vurdering er ikke automatisk lagret. Endringer krever «Lagre vurdering».')
        if not row:
            self.guided_issue.setText('Ingen funn innenfor dette utvalget.')
            self.guided_source.setText('')
            self.guided_open_xml.setEnabled(False)
            self.guided_insert_source.setEnabled(False)
            self._guided_rule_text()
            return
        self.guided_issue.setText(
            f"{row.get('source') or 'Kilde'} / {row.get('test_id') or 'Funn'} · "
            f"{row.get('severity') or 'Ukjent nivå'} · {row.get('message') or ''}")
        self.guided_source.setText('Leser dokumenterte kildeankre fra Work (ingen testkjøring)…')
        if str(row.get('source') or '') == 'Arkade 5':
            try:
                evidence = arkade_occurrences(self.work, self.snapshot, row)
                self._guided_occurrences = evidence
                self.guided_source.setText(
                    f"Arkade 5 – {len(evidence['groups'])} avvikslinje(r), "
                    f"{len(evidence['rows'])} dokumenterte XML-referanser. "
                    f"SHA-256: {evidence['source_sha256'][:20]}…  "
                    + ('Bare aggregert evidens for dette funnet; ingen XML-linjer dokumentert.'
                       if evidence['has_only_aggregate'] else ''))
                for i, anchor in enumerate(evidence['rows']):
                    item = QTreeWidgetItem([
                        str(i + 1), anchor['archive_part_title'] or anchor['archive_part_id'],
                        str(anchor['file']), str(anchor['line']), 'Ikke undersøkt',
                    ])
                    item.setData(0, Qt.ItemDataRole.UserRole, i)
                    self.guided_occurrences.addTopLevelItem(item)
                if evidence['rows']:
                    self.guided_occurrences.setCurrentItem(self.guided_occurrences.topLevelItem(0))
            except (OSError, RuntimeError, ValueError) as exc:
                self.guided_source.setText('Kildegrunnlaget kunne ikke verifiseres: ' + str(exc))
        else:
            self.guided_source.setText(
                'Ingen dokumenterte Arkade-linjer for dette funnet. Kilde: '
                + str(row.get('source_ref') or '(ikke oppgitt)'))
        self.guided_insert_source.setEnabled(bool(self._guided_occurrences and row))
        self.guided_open_xml.setEnabled(bool(self.guided_occurrences.currentItem()))
        self._guided_rule_text()

    def _guided_occurrence_selected(self, current, _previous):
        if self._guided_reader is not None:
            return
        self._guided_xml = None
        self._guided_anchor = None
        if current is not None and self._guided_occurrences:
            index = current.data(0, Qt.ItemDataRole.UserRole)
            if type(index) is int and 0 <= index < len(self._guided_occurrences['rows']):
                self._guided_anchor = self._guided_occurrences['rows'][index]
        self.guided_xml_view.setPlainText('Objektet er ennå ikke lest fra Source. Arkades linje er bevart i Work.')
        self.guided_open_xml.setEnabled(self._guided_anchor is not None)
        self._guided_rule_text()

    def _guided_inspect_xml(self):
        if self._guided_reader is not None or self._guided_anchor is None:
            return
        self._guided_reader = _XmlReader(self.work, self._guided_anchor, self)
        self._guided_reader.completed.connect(self._guided_xml_ready)
        self._guided_reader.failed.connect(self._guided_xml_failed)
        self._guided_reader.finished.connect(self._guided_xml_finished)
        self.guided_open_xml.setEnabled(False)
        self.guided_occurrences.setEnabled(False)
        self.guided_choice.setEnabled(False)
        self.guided_scope.setEnabled(False)
        self.guided_next.setEnabled(False)
        self.guided_previous.setEnabled(False)
        self.guided_xml_view.setPlainText('Leser valgt XML-forekomst fra Source (kun lesing)…')
        self._guided_reader.start()

    def _guided_xml_ready(self, result):
        self._guided_xml = result if result.get('available') else None
        if not result.get('available'):
            self.guided_xml_view.setPlainText(str(result.get('message') or 'XML er ikke tilgjengelig.'))
        else:
            meta = result.get('metadata') or {}
            self.guided_xml_view.setPlainText(
                f"KILDE: {result.get('source_path') or ''} · linje {result.get('line') or ''}\n"
                f"Objekt: {meta.get('object_type') or '?'} · ID {meta.get('system_id') or '(mangler)'}\n"
                f"Tittel: {meta.get('title') or '(mangler)'}\n"
                f"Felt: {meta.get('element') or '?'} = {meta.get('xml_value') or ''}\n"
                f"Faktisk XPath: {meta.get('xpath') or ''}\n"
                f"{result.get('provenance_note') or ''}\n\n{result.get('excerpt') or ''}")
            item = self.guided_occurrences.currentItem()
            if item is not None and self._guided_anchor and item.text(3) == str(result.get('line')):
                item.setText(4, str(meta.get('system_id') or '(ikke identifisert)'))
        self._guided_rule_text()

    def _guided_xml_failed(self, error):
        self._guided_xml = None
        self.guided_xml_view.setPlainText('Kunne ikke lese XML: ' + str(error))
        self._guided_rule_text()

    def _guided_xml_finished(self):
        self._guided_reader = None
        self.guided_occurrences.setEnabled(True)
        self.guided_choice.setEnabled(True)
        self.guided_scope.setEnabled(True)
        self.guided_open_xml.setEnabled(self._guided_anchor is not None)
        index = find_index(self._guided_rows, self._guided_selected_key)
        self.guided_previous.setEnabled(index > 0)
        self.guided_next.setEnabled(0 <= index < len(self._guided_rows) - 1)

    def _guided_rule_text(self, *_):
        row = self._guided_current
        if not row:
            self.guided_rule.setPlainText('Ingen valgt kontroll eller kilde.')
            return
        version = str(self.guided_reference_version.currentData() or '5.0')
        link = metadata_for_test(str(row.get('test_id') or ''), self._guided_bundle, version)
        field_name = link.get('xml_field') or '(ingen dokumentert XML-feltkobling)'
        name = str(link.get('metadata_id') or '(M-nummer ikke verifisert)')
        lines = [
            f"Kontroll {row.get('test_id') or ''} → XML-felt {field_name} → {name}",
            f"Noark 5 v{version} er valgt REFERANSEVERSJON, ikke automatisk verifisert uttrekksversjon.",
            'Kobling til M-felt krever entydig navn i eksisterende versjonert metadatakatalog.',
        ]
        values = link.get('standard_values') or ()
        lines.append('Registrerte standardverdier: ' + (', '.join(values) if values else 'ikke tilgjengelige'))
        condition = None
        if self._guided_bundle and link.get('metadata_id'):
            try:
                condition = delivery_condition(self._guided_bundle, version, link['metadata_id'])
            except (OSError, ValueError) as exc:
                lines.append('Kildekontroll av avleveringsbetingelsen: ' + str(exc))
        if condition:
            lines.extend((
                'Ved avlevering: ' + ', '.join(str(x) for x in condition.get('delivery_values') or ()),
                'Kilde: ' + str(condition.get('source_title') or '') +
                ', side ' + str(condition.get('page') or '?'),
            ))
        else:
            lines.append('Avleveringsbetingelse er ikke kildebekreftet for denne referanseversjonen/feltet.')
        if self._guided_xml:
            meta = self._guided_xml.get('metadata') or {}
            observed = str(meta.get('xml_value') or '')
            if str(meta.get('element') or '') == link.get('xml_field'):
                relation = inspect_relation(observed, link, condition)
                lines.extend((
                    'Faktisk verdi i inspisert objekt: ' + relation['observed'],
                    'I standardverdisettet: ' + relation['registered_code'],
                    'Ved avlevering: ' + relation['delivery_allowed'],
                ))
            else:
                lines.append('XML-elementet samsvarer ikke med kontrollens dokumenterte felt. Ingen verdikonklusjon.')
        lines.append('Arkades tekniske FEIL-status beholdes selv om verdien er registrert som standardverdi.')
        self.guided_rule.setPlainText('\n'.join(lines))

    def _guided_open_source_file(self):
        row = self._guided_current
        if row and row.get('source_ref'):
            self._open_relative(str(row['source_ref']))

    def _guided_add_source_note(self):
        if not self._guided_current or not self._guided_occurrences:
            return
        row = self._guided_current
        evidence = self._guided_occurrences
        ver = str(self.guided_reference_version.currentData() or '5.0')
        link = metadata_for_test(str(row.get('test_id') or ''), self._guided_bundle, ver)
        condition = None
        if self._guided_bundle and link.get('metadata_id'):
            try:
                condition = delivery_condition(self._guided_bundle, ver, link['metadata_id'])
            except (ValueError, OSError):
                pass
        note = review_evidence_note(row, source_sha256=evidence['source_sha256'],
                                    anchor=self._guided_anchor, xml=self._guided_xml,
                                    metadata=link, delivery=condition)
        current = self.guided_comment.toPlainText().rstrip()
        if note in current:
            return
        self.guided_comment.setPlainText(current + ('\n\n' if current else '') + note)
        self.guided_comment.setFocus()

    def _guided_mark_dirty(self, *_):
        if not self._guided_loading and self._guided_current:
            self._guided_dirty = True
            self.guided_save_note.setText('ULAGRET kommentar eller vurderingsstatus – lagre før du går videre.')

    def _guided_can_leave(self) -> bool:
        if self._guided_reader is not None:
            QMessageBox.information(self, 'XML leses', 'Avslutt lesing av XML-forekomsten før du bytter funn.')
            return False
        if not self._guided_dirty:
            return True
        reply = QMessageBox.question(
            self, 'Ulagret faglig vurdering',
            'Du har skrevet eller endret en vurdering. Forkaste den og gå videre?\n\n'
            'Velg Nei for å beholde utkastet og lagre det.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._guided_dirty = False
            return True
        return False

    def _guided_save_review(self, _checked=False, *, move_next=False):
        row = self._guided_current
        if row is None or self._guided_reader is not None:
            return
        status = str(self.guided_review_status.currentData() or '')
        explanation = self.guided_comment.toPlainText().strip()
        if not status:
            QMessageBox.information(self, 'Faglig vurdering', 'Velg en faglig status før lagring.')
            return
        if not explanation:
            QMessageBox.information(self, 'Faglig vurdering',
                                    'Beskriv hvorfor funnet vurderes slik, eller hva som må avklares.')
            return
        current_index = find_index(self._guided_rows, self._guided_selected_key)
        next_key = (self._guided_rows[current_index + 1]['finding_key']
                    if move_next and 0 <= current_index < len(self._guided_rows) - 1 else '')
        try:
            save_review(self.work, self.snapshot, row,
                        status=status, comment=explanation, user=self._get_actor(),
                        include_in_ks=self.guided_in_ks.isChecked(),
                        include_in_depot=self.guided_in_depot.isChecked())
            self._guided_dirty = False
            self._reload(select_key=str(row['finding_key']))
            self.guided_save_note.setText('Faglig vurdering lagret i Work. Teknisk kontrollstatus er uendret.')
            if next_key:
                index = find_index(self._guided_rows, next_key)
                if index >= 0:
                    self.guided_choice.setCurrentIndex(index)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kunne ikke lagre faglig vurdering', str(exc))

    def _guided_tab_changed(self, index):
        if self._guided_changing_tab or self.tabs.widget(index) is self.guided_page:
            return
        if not self._guided_can_leave():
            self._guided_changing_tab = True
            self.tabs.setCurrentWidget(self.guided_page)
            self._guided_changing_tab = False

    def _confirm_unsaved(self):
        if not self._guided_can_leave():
            return False
        return super()._confirm_unsaved()

    def _guided_stop_workers(self):
        for name in ('_guided_reader', '_guided_catalogue_worker'):
            worker = getattr(self, name, None)
            if worker is not None and worker.isRunning():
                worker.requestInterruption()
                worker.wait()

    def accept(self):
        self._guided_stop_workers()
        super().accept()

    def reject(self):
        if self._confirm_unsaved():
            self._guided_stop_workers()
            super().reject()

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted():
            self._guided_stop_workers()
