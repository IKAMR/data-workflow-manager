"""v0.2.7-a5: explicit, paged Noark 5 object navigation inside Analyse.

The existing a4 Analyse and its result, period and comment views are retained.
The Source reader runs only after a user gesture, on a cancellable QThread.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from app.noark_object_browser_v027_a5 import (
    ObjectIndexError, build_object_index, current_source_status,
    linked_delivery_findings, object_comments, object_details, object_page,
    save_object_comment,
)
from .analysis_workspace_v027_a4 import AnalysisWorkspaceDialogV4


TYPES = {
    'arkiv': 'Arkiv', 'arkivdel': 'Arkivdel',
    'mappe': 'Mappe', 'registrering': 'Registrering',
}


def _type(row: dict) -> str:
    kind = str(row.get('kind') or '')
    declared = str(row.get('xsi_type') or '').split(':')[-1].casefold()
    xml = str(row.get('xml_tag') or '').casefold()
    if kind == 'mappe' and (declared == 'saksmappe' or xml == 'saksmappe'):
        return 'Saksmappe'
    if kind == 'registrering' and (declared == 'journalpost' or xml == 'journalpost'):
        return 'Journalpost'
    return TYPES.get(kind, kind)


def _safe(value) -> str:
    return escape(str(value if value is not None and value != '' else 'Ikke oppgitt'), quote=True)


class ObjectIndexWorker(QThread):
    progressed = Signal(int)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, snapshot, parent=None):
        super().__init__(parent)
        self.snapshot = snapshot

    def run(self):
        try:
            document = build_object_index(
                self.snapshot, cancelled=self.isInterruptionRequested,
                progress=self.progressed.emit)
            self.succeeded.emit(document)
        except (OSError, ValueError, RuntimeError) as error:
            self.failed.emit(str(error))


class NoarkObjectBrowserDialog(QDialog):
    """The four first Noark levels, followed later by documents/files."""

    def __init__(self, snapshot, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.snapshot = snapshot
        self.meta = None
        self._worker = None
        self._close_when_finished = False
        self._parent_id = 0
        self._parent_title = 'Uttrekk'
        self._page = 0
        self._items = []
        self.setWindowTitle('Analyse – Noark 5-objekter – ' + snapshot.job_id)
        self.setObjectName('dwm_noark_objects_v027_a5')
        self.resize(1300, 800)
        self.setMinimumSize(900, 600)
        outer = QVBoxLayout(self)
        note = QLabel(
            'Arkiv → Arkivdel → Mapper/Saker → Registreringer/Journalposter. '
            'Velg et objekt og dobbeltklikk for neste nivå. '
            'Originaluttrekket endres ikke. Dokumentnivå følger senere.', self)
        note.setWordWrap(True)
        outer.addWidget(note)
        self.status = QLabel('Åpner objektene for valgt uttrekk…', self)
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        controls = QHBoxLayout()
        self.build_button = QPushButton('Oppdater objektlisten', self)
        self.build_button.clicked.connect(self._start)
        controls.addWidget(self.build_button)
        self.back_button = QPushButton('← Ett nivå opp', self)
        self.back_button.clicked.connect(self._back)
        controls.addWidget(self.back_button)
        self.breadcrumb = QLabel('Uttrekk', self)
        self.breadcrumb.setWordWrap(True)
        controls.addWidget(self.breadcrumb, 1)
        outer.addLayout(controls)
        filters = QHBoxLayout()
        filters.addWidget(QLabel('Vis direkte underobjekter:', self))
        self.kind = QComboBox(self)
        for label, value in (('Alle', ''), ('Arkiv', 'arkiv'), ('Arkivdel', 'arkivdel'),
                             ('Mapper / saker', 'mappe'),
                             ('Registreringer / journalposter', 'registrering')):
            self.kind.addItem(label, value)
        self.kind.currentIndexChanged.connect(self._reset_page)
        filters.addWidget(self.kind)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText('Søk i disse direkte underobjektene')
        self.search.returnPressed.connect(self._reset_page)
        filters.addWidget(self.search, 1)
        search_button = QPushButton('Søk', self)
        search_button.clicked.connect(self._reset_page)
        filters.addWidget(search_button)
        outer.addLayout(filters)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.table = QTableWidget(0, 7, splitter)
        self.table.setHorizontalHeaderLabels(
            ('Objekttype', 'System-ID', 'Tittel', 'xsi:type', 'Status', 'XML-linje', 'Underobj.'))
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._selected)
        self.table.cellDoubleClicked.connect(lambda *_: self._enter())
        for col, width in enumerate((125, 190, 290, 140, 125, 90, 90)):
            self.table.setColumnWidth(col, width)
        splitter.addWidget(self.table)
        side = QWidget(splitter)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(6, 2, 2, 2)
        self.details = QTextBrowser(side)
        self.details.setOpenExternalLinks(False)
        side_layout.addWidget(self.details, 1)
        self.comment_button = QPushButton('💬 Kommentar til valgt objekt…', side)
        self.comment_button.clicked.connect(self._save_comment)
        side_layout.addWidget(self.comment_button)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        outer.addWidget(splitter, 1)
        footer = QHBoxLayout()
        self.page_label = QLabel('', self)
        footer.addWidget(self.page_label, 1)
        self.prev_button = QPushButton('← Forrige side', self)
        self.prev_button.clicked.connect(lambda: self._move_page(-1))
        footer.addWidget(self.prev_button)
        self.next_button = QPushButton('Neste side →', self)
        self.next_button.clicked.connect(lambda: self._move_page(1))
        footer.addWidget(self.next_button)
        self.enter_button = QPushButton('Åpne underobjekter →', self)
        self.enter_button.clicked.connect(self._enter)
        footer.addWidget(self.enter_button)
        close = QPushButton('Lukk', self)
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        outer.addLayout(footer)
        self._buttons()
        self.details.setHtml('<p>DWM åpner Arkiv → Arkivdel → Mappe/Sak → Registrering/Journalpost. '
                             'Objektlisten leses fra valgt jobbs kilde, uten å endre originalfilene.</p>')
        # Opening this view is the user's explicit request to inspect Source.
        # Defer any expensive IO to the cancellable worker after Qt has started.
        QTimer.singleShot(0, self._start)

    def _buttons(self):
        ready = self.meta is not None and not (self._worker and self._worker.isRunning())
        self.back_button.setEnabled(ready and self._parent_id > 0)
        self.prev_button.setEnabled(ready and self._page > 0)
        self.next_button.setEnabled(ready and bool(getattr(self, '_has_next', False)))
        obj = self._chosen()
        self.enter_button.setEnabled(ready and obj is not None and obj.get('children', 0) > 0)
        self.comment_button.setEnabled(ready and obj is not None)
        self.build_button.setEnabled(not (self._worker and self._worker.isRunning()))
        self.kind.setEnabled(ready)
        self.search.setEnabled(ready)

    def _start(self):
        if self._worker and self._worker.isRunning():
            return
        self.status.setText('Åpner arkivstrukturen fra valgt jobb…')
        worker = ObjectIndexWorker(self.snapshot, self)
        self._worker = worker
        worker.progressed.connect(lambda n: self.status.setText(
            'Leser Noark 5-objekter… ' + str(n) + ' objekter'))
        worker.succeeded.connect(self._completed)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        worker.start()
        self._buttons()

    def _completed(self, meta):
        self.meta = meta
        self._parent_id = 0
        self._page = 0
        self._parent_title = 'Uttrekk'
        self.status.setText(current_source_status(self.snapshot, meta)
                            + ' · ' + str(meta['row_count']) + ' indekserte objekter.')
        ignored = meta.get('ignored_unanchored_elements') or {}
        if ignored:
            self.status.setText(self.status.text() + ' Elementer uten sikker plassering: '
                                + ', '.join(k + '=' + str(n) for k, n in ignored.items()))
        self._refresh_page()

    def _failed(self, message):
        self.status.setText('Objektindeks ikke tilgjengelig: ' + message)
        if not self._close_when_finished:
            QMessageBox.warning(self, 'Noark 5-objekter', message)

    def _finished(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        if self._close_when_finished:
            super().reject()
        else:
            self._buttons()

    def _chosen(self):
        i = self.table.currentRow()
        return self._items[i] if 0 <= i < len(self._items) else None

    def _reset_page(self, *_args):
        self._page = 0
        if self.meta:
            self._refresh_page()

    def _refresh_page(self):
        if self.meta is None:
            return
        try:
            data = object_page(self.snapshot, self.meta, parent_id=self._parent_id,
                               page=self._page, page_size=100,
                               search=self.search.text(),
                               kind=str(self.kind.currentData() or ''))
        except (OSError, ValueError) as exc:
            self.status.setText('Kan ikke lese den lagrede objektindeksen: ' + str(exc))
            self.meta = None
            self._items = []
            self.table.setRowCount(0)
            self._buttons()
            return
        self._items = data['rows']
        self._has_next = self._page + 1 < data['pages']
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self._items))
            for i, obj in enumerate(self._items):
                values = (_type(obj), obj['native_id'] or '—', obj['title'] or '—',
                          obj['xsi_type'] or '—', obj['status'] or '—',
                          obj['line'] or '—', obj.get('children', 0))
                for c, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    cell.setToolTip(str(value))
                    self.table.setItem(i, c, cell)
            if self._items:
                self.table.selectRow(0)
        finally:
            self.table.blockSignals(False)
        self.breadcrumb.setText(self._parent_title)
        self.page_label.setText(f"{data['total']} direkte underobjekter · "
                                f"side {self._page+1} av {max(1,data['pages'])} · "
                                f"{meta_count(self.meta)} i hele indeksen")
        self._selected()

    def _selected(self):
        obj = self._chosen()
        if obj is None or not self.meta:
            self.details.setHtml('<p>Ingen objekter på valgt side. '
                                 'Endre filter eller gå ett nivå opp.</p>')
            self._buttons()
            return
        try:
            details = object_details(self.snapshot, self.meta, obj['id'])
            finding = linked_delivery_findings(self.snapshot, self.meta, obj['id'])
            notes = object_comments(self.snapshot, self.meta, obj['id'])
        except (OSError, ValueError) as exc:
            self.details.setHtml('<p>Detaljer kan ikke verifiseres: ' + _safe(exc) + '</p>')
            self.comment_button.setEnabled(False)
            return
        fields = details['fields']
        text = '<h3>' + escape(_type(details)) + ' – ' + _safe(details['title'] or details['native_id']) + '</h3>'
        text += ('<p><b>Faktisk XML-linje:</b> ' + _safe(details['line'])
                 + '<br><b>System-ID:</b> ' + _safe(details['native_id'])
                 + '<br><b>xsi:type:</b> ' + _safe(details['xsi_type'])
                 + '<br><b>Registrert foreldrekjede:</b> '
                 + ' → '.join(escape(_type(x)) + ' ' + _safe(x['native_id'] or x['title'])
                            for x in details['ancestors']) + '</p>')
        if fields:
            text += '<h4>Lagrede, direkte XML-felt</h4><table>'
            for k, v in fields.items():
                text += '<tr><th align="left">' + _safe(k) + '</th><td>' + _safe(v) + '</td></tr>'
            text += '</table>'
        text += ('<p><b>Underobjekter:</b> ' + str(details['children']) + '</p>'
                 '<p>Visningen er en kildeprojeksjon, ikke et automatisk godkjent avvik eller vedtak.</p>')
        text += '<h4>DWM avleveringsfunn</h4><p>' + _safe(finding['note']) + '</p>'
        if finding['complete']:
            if finding['rows']:
                text += '<ul>'
                for f in finding['rows'][:50]:
                    text += '<li>' + _safe(f.get('metadata_id')) + ': ' + _safe(f.get('message')) + '</li>'
                text += '</ul>'
                if len(finding['rows']) > 50:
                    text += '<p>Flere identitetsmatchende funn finnes i Work.</p>'
            else:
                text += '<p>Ingen identitetsmatchende DWM-avleveringsfunn.</p>'
        text += '<h4>Kommentarer (felles A4-Work-register)</h4>'
        if notes:
            for note in notes[-30:]:
                text += ('<p><b>' + _safe(note.get('created_at')) + '</b> · '
                         + _safe((note.get('user') or {}).get('username'))
                         + ' · ' + _safe(note.get('annotation_type')) + '<br>'
                         + _safe(note.get('text')) + '</p>')
        else:
            text += '<p>Ingen lagrede kommentarer til dette objektet.</p>'
        self.details.setHtml(text)
        self._buttons()

    def _enter(self):
        chosen = self._chosen()
        if not chosen or not chosen.get('children'):
            return
        self._parent_id = chosen['id']
        self._parent_title = _type(chosen) + ': ' + (chosen['native_id'] or chosen['title'] or str(chosen['id']))
        self._page = 0
        self.search.clear()
        self.kind.setCurrentIndex(0)
        self._refresh_page()

    def _back(self):
        if not self._parent_id or not self.meta:
            return
        try:
            current = object_details(self.snapshot, self.meta, self._parent_id)
            new_parent = current['parent_id']
            if new_parent:
                preceding = object_details(self.snapshot, self.meta, new_parent)
                self._parent_title = _type(preceding) + ': ' + (
                    preceding['native_id'] or preceding['title'] or str(new_parent))
            else:
                self._parent_title = 'Uttrekk'
            self._parent_id = new_parent
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))
            return
        self._page = 0
        self.search.clear()
        self.kind.setCurrentIndex(0)
        self._refresh_page()

    def _move_page(self, delta):
        if self.meta is None:
            return
        next_page = max(0, self._page + delta)
        if next_page != self._page:
            self._page = next_page
            self._refresh_page()

    def _save_comment(self):
        obj = self._chosen()
        if obj is None or self.meta is None:
            return
        from app.identity_provider import LocalUserProfileIdentityProvider
        user = LocalUserProfileIdentityProvider().current_identity()
        if user is None:
            QMessageBox.information(self, 'Brukerprofil',
                                    'Registrer brukerprofil i Depotvurdering før du kommenterer.')
            return
        labels = [('Merknad', 'note'), ('Avvik / begrunnelse', 'deviation'),
                  ('Spørsmål', 'question'), ('Oppfølging', 'follow_up')]
        choices = [name for name, _value in labels]
        choice, okay = QInputDialog.getItem(self, 'Type kommentar', 'Kommentartype:', choices, 0, False)
        if not okay:
            return
        text, okay = QInputDialog.getMultiLineText(
            self, 'Kommentar til Noark-objekt',
            _type(obj) + ' / ' + (obj['native_id'] or 'uten systemID') + '\nKommentar:')
        if not okay or not text.strip():
            return
        try:
            kind = dict(labels)[choice]
            save_object_comment(self.snapshot, self.meta, obj['id'],
                                text=text.strip(), kind=kind, user=user)
            self._selected()
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, 'Kommentar', str(exc))

    def reject(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self._close_when_finished = True
            self.status.setText('Avbryter kildeindeksering uten å publisere ufullstendige filer…')
            return
        super().reject()

    def closeEvent(self, event):
        # Window-manager X must obey the same QThread cancellation contract
        # as the explicit Lukk button. Never destroy a running Qt thread.
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self._close_when_finished = True
            self.status.setText('Avbryter kildeindeksering før vinduet lukkes…')
            event.ignore()
            return
        super().closeEvent(event)


def meta_count(meta):
    return int((meta or {}).get('row_count') or 0)


class AnalysisWorkspaceDialogV5(AnalysisWorkspaceDialogV4):
    """Keep A4 controls and all A2/A3 functionality, add one object entry."""

    def __init__(self, snapshot, parent=None):
        super().__init__(snapshot, parent)
        self.setObjectName('dwm_analysis_v027_a5')
        self.object_button = QPushButton('Åpne arkivstruktur → Arkiv / Arkivdel / Saker / Journalposter', self)
        self.object_button.setToolTip('Åpner objektene i valgt uttrekk. Laster eksisterende Work-indeks eller leser registrert arkivstruktur.xml i bakgrunnen.')
        self.object_button.clicked.connect(self._open_objects)
        # Add above A4 footer. Existing Analyse layout and chart geometry stay.
        self.layout().insertWidget(self.layout().count()-1, self.object_button)

    def _open_objects(self):
        browser = NoarkObjectBrowserDialog(self.snapshot, self)
        browser.exec()


def install_analysis_workspace_v5(window) -> bool:
    """Only extends the a4 factory; classic Advanced result center is intact."""
    if not getattr(window, '_analysis_v027_a4_installed', False):
        return False
    window._analysis_dialog_class = AnalysisWorkspaceDialogV5
    window._analysis_v027_a5_installed = True
    return True
