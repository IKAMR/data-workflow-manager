"""A12: page-wise, source-bound navigation in the existing Guided KS dialog.

Uses the a4 guided dialog, a8 Arkade index, a11 DWM source bridge and the
existing a13 append-only review ledger. No new validators or approval states.
A13 exports complete recipient-specific reports from the verified A12 index.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QTreeWidgetItem, QVBoxLayout,
)

from gui_qt.ks_guided_v023_a4 import KsWorkshopDialog as _GuidedA4
from noark5_workflow.reporting.qa_paged_review_v023_a12 import (
    PagedReviewError, build_paged_index, load_review_events,
    review_page, save_review_for_page,
)
from noark5_workflow.reporting.qa_delivery_v023_a11 import DELIVERY_SOURCES


class _IndexWorker(QThread):
    complete = Signal(dict)
    failed = Signal(str)

    def __init__(self, work, snapshot, parent=None):
        super().__init__(parent)
        self.work, self.snapshot = work, snapshot

    def run(self):
        try:
            data = build_paged_index(self.work, self.snapshot,
                                     cancelled=self.isInterruptionRequested)
        except (OSError, ValueError, RuntimeError) as exc:
            self.failed.emit(str(exc))
        else:
            if not self.isInterruptionRequested():
                self.complete.emit(data)


class _CompleteReportWorker(QThread):
    """Nonblocking complete report export; cancellation discards private stage."""
    complete = Signal(dict)
    failed = Signal(str)
    advanced = Signal(int)

    def __init__(self, work, snapshot, index, target, sections, recommendation, note, parent=None):
        super().__init__(parent)
        self.work, self.snapshot, self.index, self.target = work, snapshot, index, target
        self.sections, self.recommendation, self.note = sections, recommendation, note

    def run(self):
        try:
            from noark5_workflow.reporting.qa_complete_report_v023_a13 import export_complete_reports
            result = export_complete_reports(
                self.work, self.snapshot, self.index, self.target,
                sections=self.sections, recommendation=self.recommendation,
                recommendation_note=self.note, cancelled=self.isInterruptionRequested,
                progress=self.advanced.emit)
        except (OSError, ValueError, RuntimeError) as exc:
            self.failed.emit(str(exc))
        else:
            self.complete.emit(result)


class _A19XmlReader(QThread):
    """Read one documented XML line from the selected job's Source on demand."""
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, work, anchor, parent=None):
        super().__init__(parent)
        self.work, self.anchor = work, anchor

    def run(self):
        try:
            from app.ks_xml_evidence_v023_a19 import inspect_xml_anchor
            result = inspect_xml_anchor(
                self.work, self.anchor, cancelled=self.isInterruptionRequested)
        except (OSError, ValueError, RuntimeError) as exc:
            self.failed.emit(str(exc))
        else:
            if not self.isInterruptionRequested():
                self.completed.emit(result)


class KsWorkshopDialog(_GuidedA4):
    """A4 review widgets, but selections and totals come from all indexed rows."""

    def _build_ui(self):
        self._a12_info = None
        self._a12_failed_flag = False
        self._a12_worker = None
        self._a13_export_worker = None
        self._a13_export_busy = False
        self._a12_page_no = 0
        self._a12_page_size = 100
        self._a12_page_data = None
        self._a12_reviews = {}
        self._a12_last_filters = None
        super()._build_ui()
        filters = QHBoxLayout()
        filters.addWidget(QLabel('Kilde:'))
        self.a12_source = QComboBox(self.guided_page)
        self.a12_source.setObjectName('v023_a12_source_filter')
        self.a12_source.addItem('Alle kilder', '')
        self.a12_source.currentIndexChanged.connect(self._a12_filter_changed)
        filters.addWidget(self.a12_source, 2)
        filters.addWidget(QLabel('Nivå:'))
        self.a12_level = QComboBox(self.guided_page)
        self.a12_level.setObjectName('v023_a12_severity_filter')
        self.a12_level.addItem('Alle nivåer', '')
        for item in ('ERROR', 'WARNING', 'REVIEW', 'NOTE', 'INFORMATION'):
            self.a12_level.addItem(item, item)
        self.a12_level.currentIndexChanged.connect(self._a12_filter_changed)
        filters.addWidget(self.a12_level)
        filters.addWidget(QLabel('Vurdering:'))
        self.a12_review = QComboBox(self.guided_page)
        self.a12_review.setObjectName('v023_a12_review_filter')
        self.a12_review.addItem('Alle', '')
        self.a12_review.addItem('Ikke vurdert', 'pending')
        self.a12_review.addItem('Vurdert', 'reviewed')
        self.a12_review.currentIndexChanged.connect(self._a12_filter_changed)
        filters.addWidget(self.a12_review)
        self.a12_search = QLineEdit(self.guided_page)
        self.a12_search.setObjectName('v023_a12_search')
        self.a12_search.setPlaceholderText('Søk i funn, XML-kontekst og ID…')
        self.a12_search.setClearButtonEnabled(True)
        self.a12_search.returnPressed.connect(self._a12_filter_changed)
        self.a12_search.editingFinished.connect(self._a12_filter_changed)
        filters.addWidget(self.a12_search, 2)
        self.guided_page.layout().insertLayout(1, filters)

        navigation = QHBoxLayout()
        self.a12_back = QPushButton('« Forrige side', self.guided_page)
        self.a12_back.setObjectName('v023_a12_previous_page')
        self.a12_back.clicked.connect(lambda: self._a12_go_page(-1))
        navigation.addWidget(self.a12_back)
        navigation.addWidget(QLabel('Gå til side:'))
        self.a12_page_jump = QSpinBox(self.guided_page)
        self.a12_page_jump.setObjectName('v023_a12_page_jump')
        self.a12_page_jump.setMinimum(1)
        self.a12_page_jump.setMaximum(1)
        navigation.addWidget(self.a12_page_jump)
        self.a12_jump = QPushButton('Gå', self.guided_page)
        self.a12_jump.setObjectName('v023_a12_jump')
        self.a12_jump.clicked.connect(self._a12_jump_to_page)
        navigation.addWidget(self.a12_jump)
        self.a12_counter = QLabel('Hele funnregisteret indekseres…')
        self.a12_counter.setObjectName('v023_a12_page_counter')
        navigation.addWidget(self.a12_counter, 1)
        self.a12_forward = QPushButton('Neste side »', self.guided_page)
        self.a12_forward.setObjectName('v023_a12_next_page')
        self.a12_forward.clicked.connect(lambda: self._a12_go_page(1))
        navigation.addWidget(self.a12_forward)
        self.guided_page.layout().insertLayout(2, navigation)
        self.a12_status = QLabel('Forbereder kildeverifisert visning av ALLE DWM- og Arkade-funn…')
        self.a12_status.setWordWrap(True)
        self.guided_page.layout().insertWidget(3, self.a12_status)
        self.a12_back.setEnabled(False)
        self.a12_forward.setEnabled(False)
        self.a12_jump.setEnabled(False)
        self._a12_last_filters = self._a12_filter_state()
        self.a13_export_status = QLabel('A13: Fullstendig KS-/depotrapport kan eksporteres fra Rapportutkast.')
        self.a13_export_status.setWordWrap(True)
        self.a13_cancel_export = QPushButton('Avbryt pågående rapporteksport')
        self.a13_cancel_export.setObjectName('v023_a13_cancel_export')
        self.a13_cancel_export.setEnabled(False)
        self.a13_cancel_export.clicked.connect(self._a13_cancel_export)
        report_page = self.preview_browser.parentWidget()
        report_page.layout().addWidget(self.a13_export_status)
        report_page.layout().addWidget(self.a13_cancel_export)

    def _reload(self, *, select_key: str = ''):
        if getattr(self, '_a13_export_busy', False):
            QMessageBox.warning(self, 'Eksport pågår',
                                'Ikke oppdater KS-grunnlaget før fullstendig rapporteksport er ferdig.')
            return
        self._a12_stop_index()
        self._a12_info = None
        self._a12_failed_flag = False
        self._a12_page_data = None
        self._a12_reviews = {}
        super()._reload(select_key=select_key)
        if not hasattr(self, 'a12_status'):
            return
        self.a12_status.setText('Kontrollerer originalkilder og bygger fullstendig sideindeks…')
        self.a12_counter.setText('Leser komplett kildegrunnlag…')
        self.a12_back.setEnabled(False)
        self.a12_forward.setEnabled(False)
        self.a12_jump.setEnabled(False)
        self.guided_save.setEnabled(False)
        self.guided_save_next.setEnabled(False)
        # Base _reload has already loaded and verified its bounded snapshot.
        self._a12_worker = _IndexWorker(self.work, self.snapshot, self)
        self._a12_worker.complete.connect(self._a12_ready)
        self._a12_worker.failed.connect(self._a12_failed)
        self._a12_worker.start()

    def _a12_ready(self, info):
        try:
            self._a12_info = info
            self._a12_failed_flag = False
            self._a12_reviews = load_review_events(self.work, info)
            selected = str(self.a12_source.currentData() or '')
            self.a12_source.blockSignals(True)
            self.a12_source.clear()
            self.a12_source.addItem('Alle kilder', '')
            for source, count in sorted(info['source_counts'].items()):
                self.a12_source.addItem(f'{source} ({count})', source)
            self.a12_source.setCurrentIndex(max(0, self.a12_source.findData(selected)))
            self.a12_source.blockSignals(False)
            self._a12_page_no = 0
            self._a12_last_filters = self._a12_filter_state()
            preview = len(self.all_findings)
            self.summary.setText(
                f'KS-funn totalt: {info["finding_count"]} · Enkel funntabell: '
                f'{preview} {"forhåndsviste" if preview < info["finding_count"] else "synlige"} · '
                f'Veiledet KS: alle funn sidevis · UTKAST, ingen automatisk godkjenning.')
            self.a12_status.setText(
                'Kildeverifisert indeks: alle DWM-, Arkade- og andre KS-funn er med. '
                'Teknisk status endres aldri ved faglig vurdering. '
                'Komplett KS-/depotrapport kan genereres fra fanen Rapportutkast.')
            self._a12_refill()
        except (OSError, ValueError, RuntimeError) as exc:
            self._a12_failed(str(exc))

    def _a12_failed(self, error):
        self._a12_info = None
        self._a12_failed_flag = True
        self.a12_status.setText('FULLSTENDIG KS-OPPSLAG UTILGJENGELIG: ' + error +
                                '. Veiledet KS er sperret for lagring; øvrige faner viser bare sitt eksisterende kildegrunnlag.')
        self.a12_counter.setText('Ikke dokumentert komplett – vurdering blokkert')
        self.guided_save.setEnabled(False)
        self.guided_save_next.setEnabled(False)
        self.summary.setText('KILDEKONTROLL FEILET – ikke fullstendig KS-grunnlag. '
                             'Ingen automatisk godkjenning. ' + error)
        self.a12_back.setEnabled(False)
        self.a12_forward.setEnabled(False)
        self.a12_jump.setEnabled(False)

    def _a12_filter_state(self):
        return (str(self.guided_scope.currentData() or ''),
                str(self.a12_source.currentData() or ''),
                str(self.a12_level.currentData() or ''),
                str(self.a12_review.currentData() or ''),
                self.a12_search.text())

    def _a12_restore_filters(self):
        if self._a12_last_filters is None:
            return
        current = (self.guided_scope, self.a12_source, self.a12_level, self.a12_review)
        values = self._a12_last_filters
        for box, value in zip(current, values[:4]):
            box.blockSignals(True)
            box.setCurrentIndex(max(0, box.findData(value)))
            box.blockSignals(False)
        self.a12_search.blockSignals(True)
        self.a12_search.setText(values[4])
        self.a12_search.blockSignals(False)

    def _a12_filter_changed(self, *_):
        if not self._a12_info:
            return
        if not self._guided_can_leave():
            self._a12_restore_filters()
            return
        self._a12_page_no = 0
        self._a12_refill()

    def _guided_scope_changed(self, *_):
        if not self._a12_info:
            return super()._guided_scope_changed(*_)
        self._a12_filter_changed()

    def _guided_refill(self, desired=''):
        if not self._a12_info:
            # The a4 inspector would parse/hash the entire normalized Arkade
            # JSON on its FIRST selected preview item, before A12's worker can
            # even start. Show no misleading preview as "all findings".
            if hasattr(self, 'a12_status') and self.snapshot is not None:
                self._guided_rows = ()
                self._guided_current = None
                self._guided_selected_key = ''
                self._guided_loading = True
                self.guided_choice.blockSignals(True)
                self.guided_choice.clear()
                self.guided_choice.blockSignals(False)
                self._guided_loading = False
                self.guided_issue.setText(
                    'Forbereder komplett sidevis KS-register. Kildekontroll pågår; '
                    'ingen faglige vurderinger lagres før alle funn er verifisert.')
                self.guided_source.setText('Kildedata er ennå ikke indeksert.')
                self.guided_save.setEnabled(False)
                self.guided_save_next.setEnabled(False)
                self.guided_previous.setEnabled(False)
                self.guided_next.setEnabled(False)
                return
            return super()._guided_refill(desired)
        self._a12_refill(desired=desired)

    def _a12_refill(self, desired=''):
        if not self._a12_info:
            return
        state = self._a12_filter_state()
        scope, source, level, review, search = state
        severity = 'ERROR' if scope == 'errors' else level
        try:
            page = review_page(self.work, self._a12_info,
                               page=self._a12_page_no, page_size=self._a12_page_size,
                               severity=severity, source=source, search=search,
                               reviewed=review, reviews=self._a12_reviews)
            if self._a12_page_no >= page['pages'] and page['pages']:
                self._a12_page_no = page['pages'] - 1
                page = review_page(self.work, self._a12_info,
                                   page=self._a12_page_no, page_size=self._a12_page_size,
                                   severity=severity, source=source, search=search,
                                   reviewed=review, reviews=self._a12_reviews)
        except (OSError, ValueError, RuntimeError) as exc:
            self._a12_failed(str(exc))
            return
        self._a12_page_data = page
        self._guided_rows = tuple(page['rows'])
        self._guided_loading = True
        self.guided_choice.blockSignals(True)
        self.guided_choice.clear()
        try:
            for i, item in enumerate(self._guided_rows, 1):
                marked = '✓ ' if item.get('review_status') else ''
                title = str(item.get('message') or '')[:90]
                self.guided_choice.addItem(
                    f'{marked}{self._a12_page_no * self._a12_page_size + i}. '
                    f'{item.get("test_id") or "Funn"} – {title}', item['finding_key'])
            index = next((i for i, item in enumerate(self._guided_rows)
                          if item.get('finding_key') == desired), 0)
            self.guided_choice.setCurrentIndex(index if self._guided_rows else -1)
        finally:
            self.guided_choice.blockSignals(False)
            self._guided_loading = False
        self._a12_last_filters = state
        self._guided_select(str(self.guided_choice.currentData() or ''))
        self.a12_counter.setText(
            f'Side {self._a12_page_no + 1 if page["pages"] else 0} / {page["pages"]} · '
            f'{page["total"]} treff med filtrering · {page["total_all"]} funn totalt')
        self.a12_back.setEnabled(self._a12_page_no > 0)
        self.a12_forward.setEnabled(self._a12_page_no + 1 < page['pages'])
        self.a12_page_jump.blockSignals(True)
        self.a12_page_jump.setMaximum(max(1,page['pages']))
        self.a12_page_jump.setValue(self._a12_page_no+1)
        self.a12_page_jump.blockSignals(False)
        self.a12_jump.setEnabled(page['pages'] > 1)

    def _a12_jump_to_page(self, _checked=False):
        if not self._a12_page_data or self._guided_reader is not None:
            return
        desired = self.a12_page_jump.value()-1
        if desired == self._a12_page_no:
            return
        if not 0 <= desired < self._a12_page_data['pages'] or not self._guided_can_leave():
            self.a12_page_jump.blockSignals(True)
            self.a12_page_jump.setValue(self._a12_page_no+1)
            self.a12_page_jump.blockSignals(False)
            return
        self._a12_page_no = desired
        self._a12_refill()

    def _a12_go_page(self, delta: int, *, select_last: bool = False):
        if not self._a12_page_data or self._guided_reader is not None:
            return
        next_page = self._a12_page_no + delta
        if not 0 <= next_page < self._a12_page_data['pages']:
            return
        if not self._guided_can_leave():
            return
        self._a12_page_no = next_page
        self._a12_refill()
        if select_last and self.guided_choice.count():
            self.guided_choice.setCurrentIndex(self.guided_choice.count() - 1)

    def _guided_advance(self, amount):
        if not self._a12_info:
            return super()._guided_advance(amount)
        from app.ks_guided_v023_a4 import find_index
        idx = find_index(self._guided_rows, self._guided_selected_key)
        dest = idx + amount
        if 0 <= dest < len(self._guided_rows):
            self.guided_choice.setCurrentIndex(dest)
        elif dest == len(self._guided_rows):
            self._a12_go_page(1)
        elif dest < 0:
            self._a12_go_page(-1, select_last=True)

    def _a12_anchors(self, row):
        """Only observed XML file/line pairs, never derived from aggregate counts.

        A source-report SHA (Arkade) is NOT the XML's SHA. An XML SHA is
        attached to the selected anchor only if documented separately.
        """
        from app.ks_xml_evidence_v023_a19 import documented_anchors
        data = documented_anchors(row)
        anchors = data['rows']
        if not anchors:
            self._guided_occurrences = None
            self.guided_occurrences.clear()
            self.guided_open_xml.setEnabled(False)
            self.guided_source.setText(str(data.get('message') or 'Ingen dokumentert XML-forekomst.'))
            self.guided_insert_source.setEnabled(bool(row.get('source_ref')))
            return
        source = str(row.get('source') or '')
        xml_sha = str(row.get('source_xml_sha256') or '')
        arkade_sha = (str((self._a12_info or {}).get('arkade_source_sha256') or '')
                      if source == 'Arkade 5' else '')
        self._guided_occurrences = {
            'rows': anchors, 'groups': [], 'source_sha256': xml_sha or arkade_sha,
            'source_sha256_role': ('source_xml' if xml_sha else
                                   'arkade_report' if arkade_sha else 'not_attested'),
        }
        self.guided_occurrences.clear()
        for i, anchor in enumerate(anchors):
            item = QTreeWidgetItem([
                str(i + 1), str(anchor.get('archive_part_id') or ''),
                str(anchor['file']), str(anchor['line']),
                ('Rapportert: ' + str(anchor['object_id']) if anchor.get('object_id')
                 else 'Ikke undersøkt'),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, i)
            self.guided_occurrences.addTopLevelItem(item)
        self.guided_occurrences.setCurrentItem(self.guided_occurrences.topLevelItem(0))
        self.guided_open_xml.setEnabled(True)
        self.guided_insert_source.setEnabled(True)
        hash_text = (('Dokumentert XML-SHA-256: ' + xml_sha[:20] + '…') if xml_sha else
                     ('Arkade-kilderapport SHA-256: ' + arkade_sha[:20] + '… (ikke XML-hash)')
                     if arkade_sha else 'XML-byteidentitet mot opprinnelig kontroll er ikke attestert')
        self.guided_source.setText(
            f'{source}: {data["total"]} dokumenterte XML-linjer; '
            f'{len(anchors)} vist som ankre. {hash_text}. '
            + ('Flere linjer finnes i full evidens; dette er en avgrenset visning.'
               if data.get('truncated_preview') else
               'Valgt XML leses fra Source først ved inspeksjon.'))

    def _guided_inspect_xml(self):
        """Reuse the existing Guided KS widgets; read Source off the GUI thread."""
        if self._guided_reader is not None or self._guided_anchor is None:
            return
        self._guided_reader = _A19XmlReader(self.work, self._guided_anchor, self)
        self._guided_reader.completed.connect(self._guided_xml_ready)
        self._guided_reader.failed.connect(self._guided_xml_failed)
        self._guided_reader.finished.connect(self._guided_xml_finished)
        self.guided_open_xml.setEnabled(False)
        self.guided_occurrences.setEnabled(False)
        self.guided_choice.setEnabled(False)
        self.guided_scope.setEnabled(False)
        self.guided_next.setEnabled(False)
        self.guided_previous.setEnabled(False)
        self.guided_xml_view.setPlainText('Leser faktisk XML-hierarki fra Source (kun lesing)…')
        self._guided_reader.start()

    def _guided_xml_ready(self, result):
        self._guided_xml = result if result.get('available') else None
        if not result.get('available'):
            self.guided_xml_view.setPlainText(str(result.get('message') or
                                                 'XML er ikke tilgjengelig i registrert Source.'))
            self._guided_rule_text()
            return
        meta = result.get('metadata') or {}
        chain = meta.get('hierarchy') or ()
        hierarchy = []
        for depth, level in enumerate(chain):
            label = f"{level['element']}[{level['position']}]"
            ident = str(level.get('system_id') or '')
            title = str(level.get('title') or '')
            if ident:
                label += ' · systemID: ' + ident
            if title:
                label += ' · tittel: ' + title
            hierarchy.append('  ' * depth + label)
        current_id = next((str(level['system_id']) for level in reversed(chain)
                           if level.get('system_id')), '')
        actual_xpath = str(meta.get('xpath') or '')
        text = [
            'KILDE: ' + str(result.get('source_path') or '') +
            ' · linje ' + str(result.get('line') or ''),
            'Kildeidentitet: ' + ('SHA-256 verifisert' if result.get('source_identity') ==
                                'sha256_verified' else 'Ikke attestert'),
            str(result.get('provenance_note') or ''),
            'Faktisk XPath fra XML: ' + (actual_xpath or 'Ikke entydig bestemt'),
            'Rapportert XPath fra funn: ' + str(result.get('reported_xpath') or '(ikke oppgitt)'),
            'Rapportert arkivdel-ID: ' + str(result.get('reported_archive_part_id') or '(ikke oppgitt)'),
            'Rapportert objekt-ID: ' + str(result.get('reported_object_id') or '(ikke oppgitt)'),
            'Faktisk systemID i valgt XML-hierarki: ' + (current_id or '(ikke funnet)'),
            'Faktisk XML-felt/verdi: ' + str(meta.get('element') or '(ikke bestemt)') +
            ' = ' + str(meta.get('xml_value') or ''),
            'Faktisk observert hierarki (ordinal, søskentotal ukjent):',
            *([*hierarchy] if hierarchy else ['Ingen entydig XML-starttagg på angitt linje.']),
            str(meta.get('note') or ''),
            '', str(result.get('excerpt') or ''),
        ]
        self.guided_xml_view.setPlainText('\n'.join(text))
        item = self.guided_occurrences.currentItem()
        if (item is not None and self._guided_anchor and
                item.text(3) == str(result.get('line')) and current_id):
            item.setText(4, current_id)
        self._guided_rule_text()

    def _a12_select_indexed(self, key, row):
        """Avoid old Arkade inspector's >20 MiB full-file JSON parse per click."""
        self._guided_selected_key = str(key)
        self._guided_current = row
        self._guided_anchor = None
        self._guided_xml = None
        self._guided_occurrences = None
        self.guided_occurrences.clear()
        self.guided_xml_view.setPlainText('Velg dokumentert XML-linje for inspeksjon fra Source.')
        self.guided_save.setEnabled(True)
        self.guided_save_next.setEnabled(True)
        self.guided_source_file.setEnabled(bool(row.get('source_ref')))
        self._guided_loading = True
        try:
            self.guided_review_status.setCurrentIndex(max(0, self.guided_review_status.findData(
                row.get('review_status') or '')))
            self.guided_comment.setPlainText(str(row.get('review_comment') or ''))
            self.guided_in_ks.setChecked(bool(row.get('include_in_ks',True)))
            self.guided_in_depot.setChecked(bool(row.get('include_in_depot',True)))
        finally:
            self._guided_loading = False
        self._guided_dirty = False
        self.guided_issue.setText(
            f'{row.get("source") or "Kilde"} / {row.get("test_id") or "Funn"} · '
            f'{row.get("severity") or "Ukjent"} · {row.get("message") or ""}')
        self.guided_save_note.setText('Vurderingen er ikke lagret før du trykker «Lagre».')
        self._a12_anchors(row)
        self._guided_rule_text()

    def _guided_select(self, key):
        if not self._a12_info:
            super()._guided_select(key)
            if self._a12_failed_flag or self._a12_worker is not None:
                self.guided_save.setEnabled(False)
                self.guided_save_next.setEnabled(False)
            return
        row = next((x for x in self._guided_rows if x.get('finding_key') == key), None)
        large_arkade = (bool(self._a12_info.get('arkade_index_sha256')) and
                        row is not None and row.get('source') == 'Arkade 5')
        if large_arkade:
            self._a12_select_indexed(key,row)
        else:
            super()._guided_select(key)
            if row is not None and (row.get('file') and row.get('lines')):
                self._a12_anchors(row)
                self._guided_rule_text()
        if self._a12_page_data:
            from app.ks_guided_v023_a4 import find_index
            i = find_index(self._guided_rows,key)
            ordinal = self._a12_page_no*self._a12_page_size + i + 1 if i >= 0 else 0
            self.guided_progress.setText(
                f'Funn {ordinal} av {self._a12_page_data["total"]} filtrerte '
                f'({self._a12_info["finding_count"]} totalt, '
                f'{len(self._a12_reviews)} vurdert)')
            self.guided_previous.setEnabled(ordinal > 1)
            self.guided_next.setEnabled(ordinal > 0 and ordinal < self._a12_page_data['total'])

    def _guided_rule_text(self,*args):
        row = getattr(self,'_guided_current',None)
        if not getattr(self,'_a12_info',None) or not row or row.get('source') not in DELIVERY_SOURCES:
            return super()._guided_rule_text(*args)
        version = str(row.get('noark_version') or 'ukjent')
        mid = str(row.get('metadata_id') or '')
        lines = [f'DWM-kontroll {row.get("test_id") or ""} · {mid}',
                 f'Faktisk bekreftet XSD-versjon: Noark 5 v{version}',
                 f'Faktisk dokumentert XPath: {row.get("xpath") or ""}',
                 f'XML-linjer: {row.get("lines") or []}',
                 f'Objekt-ID: {row.get("object_id") or "(mangler)"}',
                 f'Arkivdel-ID: {row.get("archive_part_id") or "(mangler)"}',
                 f'Produksjonsverdi registrert: {row.get("standard_value")}',
                 f'Tillatt ved avlevering etter kildebundet regel: {row.get("delivery_value")}',
                 f'Kilde: {row.get("source_ref") or ""}',
                 'Denne kontrollens tekniske status er uavhengig av faglig vurdering.']
        if row.get('source') == 'DWM periodekonsistens':
            lines.append('Periodekonsistens er REVIEW, ikke normativ avleverings-ERROR.')
        self.guided_rule.setPlainText('\n'.join(lines))

    def _guided_add_source_note(self):
        row = self._guided_current
        if not self._a12_info or not row:
            return super()._guided_add_source_note()
        # The inherited helper is Arkade-specific; never label an unrelated
        # DWM finding as an Arkade control in a saved human note.
        if row.get('source') not in DELIVERY_SOURCES and row.get('source') != 'Arkade 5':
            if not self._guided_occurrences or not self._guided_anchor:
                return
            anchor = self._guided_anchor
            xml = self._guided_xml if isinstance(self._guided_xml, dict) else None
            metadata = (xml or {}).get('metadata') or {}
            note = ('KILDEHENVISNING FOR FAGLIG VURDERING – IKKE VEDTAK\n'
                    'Funnkilde: ' + str(row.get('source') or '') + '\n'
                    'Test: ' + str(row.get('test_id') or '') + '\n'
                    'Evidens i Work: ' + str(row.get('source_ref') or '') + '\n'
                    'Dokumentert XML-anker: ' + str(anchor.get('file') or '') +
                    ' linje ' + str(anchor.get('line') or '') + '\n'
                    'Rapportert XPath: ' + str(anchor.get('reported_xpath') or '(ikke oppgitt)') + '\n'
                    'Faktisk XPath i nåværende XML: ' +
                    str(metadata.get('xpath') or '(ikke inspisert eller ikke entydig)') + '\n'
                    'Kildeidentitet XML: ' + ('SHA-256 verifisert' if xml and
                        xml.get('source_identity') == 'sha256_verified' else
                        'ikke attestert mot opprinnelig kontroll'))
            before = self.guided_comment.toPlainText().rstrip()
            if note not in before:
                self.guided_comment.setPlainText(before + ('\n\n' if before else '') + note)
                self.guided_comment.setFocus()
            return
        if row.get('source') == 'Arkade 5':
            return super()._guided_add_source_note()
        note = ('DWM-kilde: '+str(row.get('source_ref') or '')+'\n'
                'Funn-ID: '+str(row.get('finding_uid') or '')+'\n'
                'XML: '+str(row.get('file') or '')+' linje '+str(row.get('lines') or [])+'\n'
                'XPath: '+str(row.get('xpath') or '')+'\n'
                'Kilde-SHA-256: '+str(row.get('source_xml_sha256') or ''))
        before = self.guided_comment.toPlainText().rstrip()
        if note not in before:
            self.guided_comment.setPlainText(before+('\n\n' if before else '')+note)

    def _a12_save_review(self, _checked=False, *, move_next=False):
        if not self._a12_info:
            QMessageBox.warning(self, 'Fullstendig KS ikke tilgjengelig',
                                'Kildeverifisert sideindeks må være klar før faglig lagring.')
            return
        row = self._guided_current
        if row is None or self._guided_reader is not None:
            return
        status = str(self.guided_review_status.currentData() or '')
        comment = self.guided_comment.toPlainText().strip()
        if not status or not comment:
            QMessageBox.information(self,'Faglig vurdering',
                                    'Velg en status og skriv begrunnelse før du lagrer.')
            return
        from app.ks_guided_v023_a4 import find_index
        selected = find_index(self._guided_rows,self._guided_selected_key)
        next_key = (self._guided_rows[selected+1]['finding_key']
                    if move_next and 0 <= selected < len(self._guided_rows)-1 else '')
        advance_page = (move_next and not next_key and
                        self._a12_page_data and self._a12_page_no+1 < self._a12_page_data['pages']
                        and self.a12_review.currentData() != 'pending')
        try:
            event = save_review_for_page(self.work,self.snapshot,self._a12_info,row,
                                         status=status,comment=comment,user=self._get_actor(),
                                         include_in_ks=self.guided_in_ks.isChecked(),
                                         include_in_depot=self.guided_in_depot.isChecked())
            self._a12_reviews[row['finding_key']] = event
            self._guided_dirty = False
            # Keep this in-memory preview coherent without loading huge evidence.
            for item in self.all_findings:
                if item.get('finding_key') == row['finding_key']:
                    item.update(review_status=status,review_comment=comment,
                                include_in_ks=self.guided_in_ks.isChecked(),
                                include_in_depot=self.guided_in_depot.isChecked())
            self._a12_refill(desired=next_key or row['finding_key'])
            if next_key:
                i = find_index(self._guided_rows,next_key)
                if i >= 0:
                    self.guided_choice.setCurrentIndex(i)
            elif advance_page:
                self._a12_go_page(1)
            elif move_next and self.a12_review.currentData() == 'pending' and self.guided_choice.count():
                # Saving removes this row from the Pending filter; the next
                # pending issue shifts into its old position in the same page.
                self.guided_choice.setCurrentIndex(min(selected, self.guided_choice.count()-1))
            self.guided_save_note.setText(
                'Faglig vurdering lagret i Work. Teknisk FEIL/REVIEW-status er uendret.')
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self,'Kunne ikke lagre vurdering',str(exc))

    def _preview(self):
        if not self._a12_info or self._a13_export_busy:
            QMessageBox.warning(self, 'Rapportgrunnlag ikke klart',
                                'Komplett og verifisert A12-indeks må være klar før rapportvisning.')
            return
        if self._guided_dirty or self._unsaved:
            QMessageBox.warning(self, 'Ulagret faglig vurdering',
                                'Lagre eller forkast endringer før rapportvisning.')
            return
        try:
            from noark5_workflow.reporting.qa_complete_report_v023_a13 import preview_complete_summary
            summary = preview_complete_summary(
                self.work, self.snapshot, self._a12_info,
                sections=self._report_sections(),
                recommendation=self.recommendation.currentData(),
                recommendation_note=self.recommendation_note.toPlainText())
            self.preview_browser.setHtml(summary)
            self.a13_export_status.setText(
                'Kildeverifisert totaloversikt. Alle enkeltfunn eksporteres først '
                'ved «Generer KS-/godkjenningsrapport…»; oversikten er ikke et formelt vedtak.')
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kan ikke vise komplett rapportgrunnlag', str(exc))

    def _export(self):
        if not self._a12_info or self._a13_export_busy:
            QMessageBox.warning(self, 'Rapporteksport ikke klar',
                                'Komplett A12-indeks må være tilgjengelig, og ingen annen eksport må kjøre.')
            return
        if self._guided_dirty or self._unsaved:
            QMessageBox.warning(self, 'Ulagrede endringer',
                                'Lagre eller forkast alle faglige endringer før eksport.')
            return
        if self.recommendation.currentData() != 'pending' and not self._recommendation_saved:
            QMessageBox.warning(self, 'Innstilling er ikke lagret',
                                'Lagre innstillingen som en dokumentert KS-observasjon før eksport.')
            return
        from pathlib import Path
        from datetime import datetime
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(
            self, 'Velg overordnet mappe for fullstendig rapportpakke', str(Path.home()))
        if not folder:
            return
        ident = self.snapshot.get('work_identity') or {}
        safe = ''.join(c if c.isascii() and (c.isalnum() or c in '-_') else '_'
                       for c in str(ident.get('job_id') or 'JOB'))
        target = Path(folder) / ('KS_DEPOT_' + safe + '_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        reply = QMessageBox.question(
            self, 'Fullstendig KS- og depotrapport – UTKAST',
            f'Alle {self._a12_info["finding_count"]} verifiserte funn eksporteres i begge '
            'rapporter. Faglige kommentarer vises bare der de er valgt. '
            'Ingen formell depotgodkjenning eller nytt testresultat opprettes.\n\n'
            + str(target),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._a13_export_busy = True
        self.a13_cancel_export.setEnabled(True)
        self.a13_export_status.setText('Eksporterer alle funn – rapporten publiseres først når den er komplett…')
        self._a13_export_worker = _CompleteReportWorker(
            self.work, self.snapshot, self._a12_info, target, self._report_sections(),
            str(self.recommendation.currentData() or 'pending'),
            self.recommendation_note.toPlainText(), self)
        self._a13_export_worker.complete.connect(self._a13_report_ready)
        self._a13_export_worker.failed.connect(self._a13_report_failed)
        self._a13_export_worker.advanced.connect(self._a13_report_progress)
        self._a13_export_worker.finished.connect(self._a13_report_finished)
        self._a13_export_worker.start()

    def _a13_report_progress(self, count):
        self.a13_export_status.setText(
            f'Komplett rapporteksport: {count} av {self._a12_info["finding_count"]} funn behandlet…')

    def _a13_report_ready(self, report):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        self._report_path = report['index']
        self.a13_export_status.setText(
            f'Komplett rapportpakke ferdig: {report["finding_count"]} funn · '
            f'{report["reviews_in_ks"]} KS-kommentarer · '
            f'{report["reviews_in_depot"]} depotkommentarer. UTKAST.')
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._report_path)))
        QMessageBox.information(
            self, 'Komplett KS-/depotrapport generert',
            'Hele det kildebundne registeret er eksportert til:\n'
            + str(report['directory']) + '\n\nIngen formell godkjenning er registrert.')

    def _a13_report_failed(self, error):
        self.a13_export_status.setText('Eksport feilet eller ble avbrutt; ingen ufullstendig rapport publisert.')
        QMessageBox.warning(self, 'Komplett rapporteksport feilet', error)

    def _a13_report_finished(self):
        self._a13_export_busy = False
        self.a13_cancel_export.setEnabled(False)
        self._a13_export_worker = None

    def _a13_cancel_export(self, _checked=False):
        worker = getattr(self, '_a13_export_worker', None)
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            self.a13_export_status.setText('Avbryter eksport og rydder midlertidige filer…')

    def _new_observation(self, context: str):
        if self._a13_export_busy:
            QMessageBox.warning(self, 'Eksport pågår',
                                'Ingen nye observasjoner kan registreres under eksport.')
            return
        return super()._new_observation(context)

    def _save_recommendation(self):
        if self._a13_export_busy:
            QMessageBox.warning(self, 'Eksport pågår',
                                'Ikke endre den faglige innstillingen under eksport.')
            return
        return super()._save_recommendation()

    def _guided_save_review(self, _checked=False, *, move_next=False):
        if self._a13_export_busy:
            QMessageBox.warning(self, 'Eksport pågår',
                                'Ikke lagre en ny vurdering mens rapporten publiseres.')
            return
        return self._a12_save_review(_checked, move_next=move_next)

    def _a12_stop_index(self):
        worker = getattr(self,'_a12_worker',None)
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            worker.wait()
        self._a12_worker = None

    def _guided_stop_workers(self):
        self._a13_cancel_export()
        export_worker = getattr(self, '_a13_export_worker', None)
        if export_worker is not None and export_worker.isRunning():
            export_worker.wait()
        self._a12_stop_index()
        super()._guided_stop_workers()
