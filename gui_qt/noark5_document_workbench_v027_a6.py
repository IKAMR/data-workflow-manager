"""DWM v0.2.7-a6: direct Noark level selector and working document-file view.

A5's object inspection remains available for sampling. This is a second,
control-oriented route: choose scope/status/level without drilling N times.
Only the document-file section is fully operational in this increment.
"""
from __future__ import annotations

from html import escape
import json
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QTextBrowser, QVBoxLayout, QWidget,
)

from app.noark5_document_workbench_v027_a6 import (
    PSEUDO, DocumentWorkbenchError, arkade_raf_by_puid,
    build_document_index, copy_selected_files, file_page, find_document_index,
    format_annotations, format_groups, format_policy_label,
    latest_assessment, save_format_annotation,
)
from app.analysis_workspace_v027_a2 import part_identity, summary_counts
from app.format_assessment_v0111_a2 import (
    FORMAT_SOURCE_NASJONALARKIVET, FORMAT_SOURCE_ARKADE_RAF,
    chosen_format_source,
)
from .noark_object_browser_v027_a5 import AnalysisWorkspaceDialogV5

LEVELS = (
    ('Arkiv', 'arkiv'), ('Arkivdel', 'arkivdel'),
    ('Klassifikasjonssystem', 'klassifikasjonssystem'), ('Klasse', 'klasse'),
    ('Mappe / Sak', 'mappe'), ('Registrering / Journalpost', 'registrering'),
    ('Dokumentbeskrivelse', 'dokumentbeskrivelse'),
    ('Dokumentobjekt', 'dokumentobjekt'), ('Dokumentfil / Filformat', 'dokumentfil'),
)


class DocumentWorker(QThread):
    progress = Signal(int, int)
    success = Signal(object)
    failure = Signal(str)

    def __init__(self, snapshot, *, copy_args=None, parent=None):
        super().__init__(parent)
        self.snapshot = snapshot
        self.copy_args = copy_args

    def run(self):
        try:
            if self.copy_args:
                result = copy_selected_files(
                    self.snapshot, **self.copy_args,
                    cancelled=self.isInterruptionRequested,
                    progress=lambda done, total: self.progress.emit(done, total))
            else:
                result = build_document_index(
                    self.snapshot, cancelled=self.isInterruptionRequested,
                    progress=lambda done: self.progress.emit(done, 0))
            self.success.emit(result)
        except Exception as exc:
            self.failure.emit(str(exc))  # Worker failures must return to Qt.


def _h(raw):
    return escape(str(raw if raw not in (None, '') else '–'), quote=True)


def _source_label(mode):
    return ('Nasjonalarkivet – datert formatliste'
            if mode == FORMAT_SOURCE_NASJONALARKIVET
            else 'Arkade 5 – historisk RAF-220301')


class Noark5ControlWorkspace(QDialog):
    """Single forward-looking control path; direct jump to any level."""

    def __init__(self, snapshot, settings=None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.snapshot = snapshot
        self.meta = None
        self._worker = None
        self._copy_mode = False
        self._close_later = False
        self._page = 0
        self._rows = []
        self._groups = []
        self._raf = {}
        self._assessment_cache = {}
        self._preferred_puid = ""
        self._loading = False
        self.setWindowTitle('Analyse – Noark 5-kontroller og dokumentfiler – ' + snapshot.job_id)
        self.setObjectName('dwm_noark5_controls_v027_a6')
        self.resize(1430, 860)
        self.setMinimumSize(950, 600)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 9, 10, 9)
        outer.setSpacing(7)

        intro = QLabel('Kontrollorientert Noark 5-visning: velg nivå direkte. '
                       'Filformatene kommer fra dokumentert Siegfried-evidens, '
                       'vurderingsgrunnlaget fra Setup og kommentarer fra samme Work-register som Analyse.', self)
        intro.setWordWrap(True)
        outer.addWidget(intro)

        selections = QHBoxLayout()
        selections.addWidget(QLabel('Nivå:'))
        self.level = QComboBox(self)
        for name, code in LEVELS:
            self.level.addItem(name, code)
        self.level.setCurrentIndex(self.level.findData('dokumentfil'))
        self.level.currentIndexChanged.connect(self._level_changed)
        selections.addWidget(self.level, 2)
        selections.addWidget(QLabel('Omfang:'))
        self.scope = QComboBox(self)
        self.scope.addItem('Hele uttrekket', '')
        for i, part in enumerate(snapshot.parts):
            key = str(part_identity(part).get('system_id') or '')
            if key:
                label = str(part_identity(part).get('title') or 'Arkivdel ' + str(i + 1))
                self.scope.addItem('Arkivdel: ' + label, key)
        self.scope.currentIndexChanged.connect(self._scope_changed)
        selections.addWidget(self.scope, 3)
        selections.addWidget(QLabel('Status:'))
        self.status_filter = QComboBox(self)
        for name, code in (('Alle', 'all'), ('Faglig avvik', 'deviation'),
                           ('Faglig akseptert', 'accepted'), ('Til avklaring', 'clarify'),
                           ('Uten faglig vurdering', 'unreviewed'),
                           ('Uidentifisert / flertydig', 'unknown'),
                           ('Finnes i valgt formatliste', 'profile')):
            self.status_filter.addItem(name, code)
        self.status_filter.currentIndexChanged.connect(self._apply_filter)
        selections.addWidget(self.status_filter, 2)
        outer.addLayout(selections)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel('Formatvurdering:'))
        self.authority = QComboBox(self)
        self.authority.addItem('Nasjonalarkivet – datert liste', FORMAT_SOURCE_NASJONALARKIVET)
        self.authority.addItem('Arkade 5 – historisk RAF', FORMAT_SOURCE_ARKADE_RAF)
        try:
            mode = chosen_format_source(settings)
        except (ValueError, TypeError, AttributeError):
            mode = FORMAT_SOURCE_NASJONALARKIVET
        self.authority.setCurrentIndex(max(0, self.authority.findData(mode)))
        self.authority.currentIndexChanged.connect(self._apply_filter)
        mode_row.addWidget(self.authority, 2)
        self.source_note = QLabel('Bytte her er bare en visning. Varig standard velges i Setup.', self)
        self.source_note.setWordWrap(True)
        mode_row.addWidget(self.source_note, 3)
        self.reload = QPushButton('Oppdater filregisteret', self)
        self.reload.clicked.connect(self._start_index)
        mode_row.addWidget(self.reload)
        outer.addLayout(mode_row)

        self.status = QLabel('Åpner eksisterende dokumentregister eller leser ferdig Siegfried-kjøring…', self)
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 3, 0)
        caption = QLabel('Filtyper fra valgt uttrekk (avmerk for filtrering og kopiering)', left)
        caption.setWordWrap(True)
        left_layout.addWidget(caption)
        all_buttons = QHBoxLayout()
        select_all = QPushButton('Merk alle', left)
        select_all.clicked.connect(lambda: self._mark_all(True))
        all_buttons.addWidget(select_all)
        select_none = QPushButton('Fjern alle', left)
        select_none.clicked.connect(lambda: self._mark_all(False))
        all_buttons.addWidget(select_none)
        left_layout.addLayout(all_buttons)
        self.types = QListWidget(left)
        self.types.itemChanged.connect(self._apply_filter)
        self.types.currentItemChanged.connect(self._chosen_type_changed)
        left_layout.addWidget(self.types, 1)
        splitter.addWidget(left)

        middle = QWidget(splitter)
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(3, 0, 3, 0)
        search_row = QHBoxLayout()
        self.search = QLineEdit(middle)
        self.search.setPlaceholderText('Søk i filnavn, PUID, format og dokumentobjekt')
        self.search.returnPressed.connect(self._reset_page)
        search_row.addWidget(self.search, 1)
        search_button = QPushButton('Søk', middle)
        search_button.clicked.connect(self._reset_page)
        search_row.addWidget(search_button)
        middle_layout.addLayout(search_row)
        self.files = QTableWidget(0, 6, middle)
        self.files.setHorizontalHeaderLabels(('PUID', 'Fil / relativ sti', 'Format', 'Bytes', 'Arkivdel', 'Dokumentobjekt'))
        self.files.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.files.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.files.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.files.setAlternatingRowColors(True)
        self.files.verticalHeader().hide()
        self.files.itemSelectionChanged.connect(self._selected_file_changed)
        for i, width in enumerate((110, 280, 175, 90, 120, 135)):
            self.files.setColumnWidth(i, width)
        middle_layout.addWidget(self.files, 1)
        pager = QHBoxLayout()
        self.page_info = QLabel('Filregisteret er ikke åpnet', middle)
        pager.addWidget(self.page_info, 1)
        self.prev = QPushButton('← Forrige', middle)
        self.prev.clicked.connect(lambda: self._step_page(-1))
        pager.addWidget(self.prev)
        self.next = QPushButton('Neste →', middle)
        self.next.clicked.connect(lambda: self._step_page(1))
        pager.addWidget(self.next)
        middle_layout.addLayout(pager)
        splitter.addWidget(middle)

        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(3, 0, 0, 0)
        right_layout.addWidget(QLabel('Filformatvurdering, kilde og faglige merknader', right))
        self.details = QTextBrowser(right)
        self.details.setOpenExternalLinks(False)
        right_layout.addWidget(self.details, 1)
        self.review_button = QPushButton('Faglig vurdering / merknad…', right)
        self.review_button.clicked.connect(self._edit_review)
        right_layout.addWidget(self.review_button)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 3)
        outer.addWidget(splitter, 1)
        self.splitter = splitter
        self.level_help = QTextBrowser(self)
        self.level_help.setOpenExternalLinks(False)
        outer.addWidget(self.level_help, 1)
        self.object_bridge = QPushButton('Åpne objektnavigasjonen (a5) for stikkprøver…', self)
        self.object_bridge.clicked.connect(self._open_object_browser)
        outer.addWidget(self.object_bridge)

        action_row = QHBoxLayout()
        self.copy_flat = QComboBox(self)
        self.copy_flat.addItem('PUID-undermapper (standard)', 'puid')
        self.copy_flat.addItem('Flat mappe (navnekollisjoner løses)', 'flat')
        action_row.addWidget(QLabel('Kopieringsstruktur:'))
        action_row.addWidget(self.copy_flat, 2)
        self.copy_button = QPushButton('Kopier filtrerte filtyper til valgt område…', self)
        self.copy_button.clicked.connect(self._copy_selected)
        action_row.addWidget(self.copy_button, 2)
        close_button = QPushButton('Lukk', self)
        close_button.clicked.connect(self.reject)
        action_row.addWidget(close_button)
        outer.addLayout(action_row)
        self._shell()
        QTimer.singleShot(0, self._start_index)

    def _level_changed(self, *_):
        self._page = 0
        self._shell()
        if self.level.currentData() in ('dokumentfil', 'dokumentobjekt', 'dokumentbeskrivelse'):
            self._refresh_groups()

    def _shell(self):
        kind = self.level.currentData()
        documents = kind in ('dokumentfil', 'dokumentobjekt', 'dokumentbeskrivelse')
        self.splitter.setVisible(documents)
        self.level_help.setVisible(not documents)
        self.object_bridge.setVisible(not documents)
        self.copy_flat.setEnabled(documents)
        self.copy_button.setEnabled(documents and bool(self.meta) and not self._worker_running())
        self.review_button.setEnabled(documents and bool(self.meta))
        if not documents:
            name = next((label for label, code in LEVELS if code == kind), kind)
            counts = summary_counts(self.snapshot)
            self.status.setText(
                name + ' – strukturelt kontrollnivå (skall i a6). '
                'A5-objektnavigasjonen brukes til detaljer og stikkprøver. '
                'Resultatgrunnlag: ' + str(counts) + '. '
                'Komplette regel-/XSD-/XPath-kontroller for dette nivået er ikke samlet i denne visningen ennå.')
            self.level_help.setHtml('<h3>' + _h(name) + '</h3>'
                '<p>Dette kontrollnivået er etablert som direkte inngang.</p>'
                '<p>Foreløpig er dette et skall; det betyr ikke at alle Noark 5-krav er kontrollert.</p>'
                '<p><b>Bruk a5-objektnavigasjonen</b> for å inspisere virkelige arkivobjekter '
                'og XML-metadata. Kravhenvisninger og fullstendige testfunn per nivå '
                'samles her i senere utvikling.</p>')
        elif self.meta:
            message = 'Dokumentnivå: ' + str(self.meta['files_total']) + ' filoppføringer fra valgt Work/Siegfried.'
            if kind in ('dokumentobjekt', 'dokumentbeskrivelse'):
                message += (' Bare dokumentobjekter/-beskrivelser med entydig filreferanse '
                            'kan kobles til formatlisten. Ikke en komplett objektoversikt.')
            self.status.setText(message)

    def _scope_changed(self, *_):
        self._page = 0
        self._refresh_groups()

    def _worker_running(self):
        return self._worker is not None and self._worker.isRunning()

    def _open_object_browser(self):
        from .noark_object_browser_v027_a5 import NoarkObjectBrowserDialog
        dialog = NoarkObjectBrowserDialog(self.snapshot, self)
        dialog.exec()

    def _start_index(self):
        if self._worker_running():
            return
        self.meta = None
        self.status.setText('Bygger eller åpner kildeverifisert dokumentregister i Work…')
        self._launch(DocumentWorker(self.snapshot, parent=self), copying=False)

    def _launch(self, worker, *, copying):
        self._worker = worker
        self._copy_mode = copying
        worker.progress.connect(self._progress)
        worker.success.connect(self._completed)
        worker.failure.connect(self._failed)
        worker.finished.connect(self._finished)
        worker.start()
        self._buttons()

    def _progress(self, done, total):
        if self._copy_mode:
            self.status.setText(f'Kopierer og verifiserer: {done} av {total} dokumentfiler…')
        else:
            self.status.setText(f'Leser filresultater i Work: {done} filer…')

    def _completed(self, value):
        if self._copy_mode:
            self.status.setText('Kopiert ' + str(value['files_copied']) + ' filer til ' + value['path'])
            QMessageBox.information(self, 'Filkopiering fullført',
                                    f"{value['files_copied']} filer kopiert og verifisert.\n\n"
                                    f"Mål: {value['path']}\n\nManifest: {value['manifest']}")
            return
        self.meta = value
        self._raf = arkade_raf_by_puid(Path(self.snapshot.work))
        self._load_assessment_cache()
        self.status.setText('Siegfried: ' + str(value['files_total']) + ' individuelle filer, '
                            + str(value['formats_total']) + ' PUID-/identifikasjonsgrupper. '
                            'Arkivdelkobling: ' + str(value.get('xml_mapping', {}).get('state') or 'ukjent')
                            + ' (' + str(value.get('linked_files', 0)) + ' koblet, '
                            + str(value.get('unlinked_files', 0)) + ' uten entydig kobling).')
        self._refresh_groups()

    def _failed(self, message):
        self.status.setText(('Kopiering' if self._copy_mode else 'Dokumentregister') + ': ' + message)
        if not self._close_later:
            QMessageBox.warning(self, 'Noark 5 dokumenter', message)

    def _finished(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self._buttons()
        if not self._copy_mode and self.meta is not None and not self._close_later:
            self._refresh_groups()
        if self._close_later:
            super().reject()

    def _buttons(self):
        busy = self._worker_running()
        self.reload.setEnabled(not busy)
        self.copy_button.setEnabled(not busy and bool(self.meta) and self.level.currentData() in (
            'dokumentfil', 'dokumentobjekt', 'dokumentbeskrivelse'))
        self.review_button.setEnabled(not busy and bool(self.meta))

    def _load_assessment_cache(self):
        from noark5_workflow.analysis.depot_annotations import list_depot_annotations
        cache = {}
        notes = list_depot_annotations(self.snapshot.report_path, view_id='analysis')
        prefix = 'analysis-a6:'
        for note in notes:
            target = note.get('target') or {}
            ident = target.get('target_id') or ''
            if not isinstance(ident, str) or not ident.startswith(prefix):
                continue
            try:
                values = json.loads(ident[len(prefix):])
            except (ValueError, TypeError):
                continue
            if not (isinstance(values, list) and len(values) == 2
                    and values[0] == self.meta.get('run_raw_sha256')):
                continue
            status = str(target.get('target_type') or '')
            if status.startswith('format_assessment_'):
                code = status[len('format_assessment_'):]
                if code in ('accepted', 'deviation', 'clarify'):
                    cache[str(values[1])] = code
        self._assessment_cache = cache

    def _part(self):
        return str(self.scope.currentData() or '')

    def _refresh_groups(self):
        if not self.meta or self._worker_running() or self.level.currentData() not in (
                'dokumentfil', 'dokumentobjekt', 'dokumentbeskrivelse'):
            return
        try:
            all_groups = format_groups(self.snapshot, self.meta, self._part())
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))
            self._groups = []
            self.types.clear()
            self.files.setRowCount(0)
            return
        old = {self.types.item(i).data(Qt.ItemDataRole.UserRole):
               self.types.item(i).checkState() == Qt.CheckState.Checked
               for i in range(self.types.count())}
        self._groups = list(all_groups)
        self._loading = True
        self.types.clear()
        for group in self._groups:
            puid = group['puid']
            label = PSEUDO.get(puid, puid) + ' · ' + str(group['count']) + ' filer'
            if group['name'] and puid not in PSEUDO:
                label += ' · ' + group['name']
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if old.get(puid, True)
                               else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, puid)
            self.types.addItem(item)
        self._loading = False
        if self.types.count():
            self.types.setCurrentRow(0)
        self._apply_filter()

    def _mark_all(self, checked):
        self._loading = True
        for i in range(self.types.count()):
            self.types.item(i).setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._loading = False
        self._apply_filter()

    def _policy(self, puid):
        return format_policy_label(puid, str(self.authority.currentData()), raf=self._raf)

    def _selected_formats(self):
        if not self.meta:
            return ()
        checked = {self.types.item(i).data(Qt.ItemDataRole.UserRole)
                   for i in range(self.types.count())
                   if self.types.item(i).checkState() == Qt.CheckState.Checked}
        key = self.status_filter.currentData()
        chosen = []
        for row in self._groups:
            puid = row['puid']
            if puid not in checked:
                continue
            if key in ('deviation', 'accepted', 'clarify', 'unreviewed'):
                review = self._assessment_cache.get(puid, '')
                if key == 'unreviewed' and review:
                    continue
                if key != 'unreviewed' and review != key:
                    continue
            elif key == 'unknown' and puid not in PSEUDO:
                continue
            elif key == 'profile':
                label, _ = self._policy(puid)
                if (not label.startswith('Akseptert i valgt profil')
                        and not label.startswith('Arkade: Gyldig arkivformat')):
                    continue
            chosen.append(puid)
        return tuple(chosen)

    def _apply_filter(self, *_):
        if self._loading or not self.meta or self._worker_running():
            return
        self._page = 0
        self._update_page()

    def _reset_page(self, *_):
        self._page = 0
        self._update_page()

    def _update_page(self):
        if not self.meta or self._worker_running():
            return
        types = self._selected_formats()
        if not types:
            self.files.setRowCount(0)
            self._rows = []
            self.page_info.setText('Ingen avmerkede filtyper samsvarer med filteret')
            self.prev.setEnabled(False)
            self.next.setEnabled(False)
            return
        try:
            result = file_page(self.snapshot, self.meta, puids=types, part_id=self._part(),
                               search=self.search.text(), page=self._page, page_size=100)
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))
            return
        self._rows = result['rows']
        self.files.blockSignals(True)
        try:
            self.files.setRowCount(len(self._rows))
            for i, row in enumerate(self._rows):
                cells = (PSEUDO.get(row['puid'], row['puid']), row['rel'],
                         row['fmt'] or 'Ukjent', row['size'], row['part_id'] or 'Ikke koblet',
                         row['doc_id'] or 'Ikke koblet')
                for j, value in enumerate(cells):
                    item = QTableWidgetItem(str(value))
                    item.setToolTip(str(value))
                    self.files.setItem(i, j, item)
            if self._rows:
                self.files.selectRow(0)
        finally:
            self.files.blockSignals(False)
        self.page_info.setText(f"{result['total']} filer · side {self._page + 1} "
                               f"av {max(1, result['pages'])}")
        self.prev.setEnabled(self._page > 0)
        self.next.setEnabled(self._page + 1 < result['pages'])
        self._selected_file_changed()

    def _step_page(self, delta):
        self._page = max(0, self._page + delta)
        self._update_page()

    def _active_puid(self):
        return self._preferred_puid

    def _selected_file_changed(self):
        row = self.files.currentRow()
        if 0 <= row < len(self._rows):
            self._preferred_puid = self._rows[row]['puid']
        self._show_details()

    def _chosen_type_changed(self, *_):
        item = self.types.currentItem()
        if item is not None:
            self._preferred_puid = str(item.data(Qt.ItemDataRole.UserRole) or '')
        self._show_details()

    def _show_details(self):
        puid = self._active_puid()
        if not self.meta or not puid:
            self.details.setHtml('<p>Velg en filtype eller en dokumentfil.</p>')
            return
        try:
            label, explanation = self._policy(puid)
            notes = format_annotations(self.snapshot, self.meta, puid)
            current = latest_assessment(self.snapshot, self.meta, puid)
        except (OSError, ValueError) as exc:
            self.details.setHtml('<p>Kan ikke lese vurdering: ' + _h(exc) + '</p>')
            return
        row_index = self.files.currentRow()
        record = self._rows[row_index] if 0 <= row_index < len(self._rows) else None
        html = '<h3>' + _h(PSEUDO.get(puid, puid)) + '</h3>'
        html += '<p><b>Valgt grunnlag:</b> ' + _h(_source_label(self.authority.currentData())) + '</p>'
        html += '<p><b>Regel-/RAF-status:</b> ' + _h(label) + '<br>' + _h(explanation) + '</p>'
        html += '<p><b>Faglig vurdert:</b> ' + _h({
            'accepted': 'Akseptert for denne leveransen (ikke formelt vedtak)',
            'deviation': 'Avvik dokumentert', 'clarify': 'Krever avklaring',
            '': 'Ikke vurdert',
        }.get(current, 'Ukjent')) + '</p>'
        if record and record['puid'] == puid:
            html += ('<hr><b>Dokumentfil:</b> ' + _h(record['rel'])
                     + '<br><b>Størrelse:</b> ' + str(record['size']) + ' bytes'
                     + '<br><b>Siegfried:</b> ' + _h(record['ident_state'])
                     + '<br><b>Arkivdel:</b> ' + _h(record['part_id'])
                     + '<br><b>Dokumentbeskrivelse:</b> ' + _h(record['description_id'])
                     + '<br><b>Dokumentobjekt:</b> ' + _h(record['doc_id'])
                     + '<br><b>XML-linje:</b> ' + _h(record['xml_line']) + '<hr>')
        html += '<h4>Merknader (samme Work-register)</h4>'
        if notes:
            for note in notes[-30:]:
                actor = note.get('user') or {}
                html += ('<p>' + _h(note.get('created_at')) + ' · '
                         + _h(actor.get('name') or actor.get('username')) + ' · '
                         + _h(note.get('annotation_type')) + '<br>'
                         + _h(note.get('text')) + '</p>')
        else:
            html += '<p>Ingen registrerte merknader eller faglige vurderinger.</p>'
        html += '<p><i>Formatoppføring er ikke en Noark 5-testgodkjenning. '
        html += 'Arkade-status er en historisk sammenligning og kan ikke knyttes automatisk til enkeltfil.</i></p>'
        self.details.setHtml(html)

    def _edit_review(self):
        puid = self._active_puid()
        if not puid or not self.meta:
            QMessageBox.information(self, 'Filformat', 'Velg en filtype først.')
            return
        from app.identity_provider import LocalUserProfileIdentityProvider
        user = LocalUserProfileIdentityProvider().current_identity()
        if user is None:
            QMessageBox.information(self, 'Brukerprofil',
                                    'Registrer brukerprofil i Depotvurdering før du vurderer filformat.')
            return
        choices = [('Faglig akseptert som arkivformat i dette uttrekket', 'accepted', 'note'),
                   ('Avvik – må beskrives', 'deviation', 'deviation'),
                   ('Krever nærmere avklaring', 'clarify', 'question'),
                   ('Merknad', '', 'note'), ('Spørsmål', '', 'question'),
                   ('Oppfølging', '', 'follow_up'), ('Akseptabelt avvik', '', 'accepted_deviation')]
        label, ok = QInputDialog.getItem(self, 'Vurder filformat',
                                         'Vurdering / merknadstype:',
                                         [x[0] for x in choices], 0, False)
        if not ok:
            return
        note, ok = QInputDialog.getMultiLineText(
            self, 'Begrunnelse – ' + PSEUDO.get(puid, puid),
            'Begrunn valg, forutsetninger eller avvik (lagres historisert i Work):')
        if not ok or not note.strip():
            return
        _, assessment, kind = next(x for x in choices if x[0] == label)
        try:
            save_format_annotation(self.snapshot, self.meta, puid, assessment=assessment,
                                   kind=kind, text=note, user=user)
            self._load_assessment_cache()
            self._show_details()
            self._apply_filter()
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, 'Filformatvurdering', str(exc))

    def _copy_selected(self):
        if self._worker_running() or not self.meta:
            return
        selected = self._selected_formats()
        if not selected:
            QMessageBox.information(self, 'Filkopiering', 'Merk filtypene som skal kopieres først.')
            return
        path = QFileDialog.getExistingDirectory(self, 'Velg outputområde for dokumentkopier', '')
        if not path:
            return
        total = sum(row['count'] for row in self._groups if row['puid'] in selected)
        # The group totals already respect a selected, verified archive part.
        response = QMessageBox.question(
            self, 'Bekreft kopiering',
            f'Kopiere {total} dokumentfiler fra {len(selected)} valgte filtyper?\n\n'
            f'Målområde: {path}\n'
            f'Struktur: {self.copy_flat.currentText()}\n\n'
            'DWM oppretter en ny DWM-filutvalg-undermappe i valgt outputområde, '
            'kontrollerer alle kildefiler, verifiserer kopiene med SHA-256 og '
            'lager et komplett manifest. Ingen originale filer endres. Fortsette?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if response != QMessageBox.StandardButton.Yes:
            return
        args = {'meta': self.meta, 'selected_puids': selected,
                'destination': path, 'structure': str(self.copy_flat.currentData()),
                'part_id': self._part()}
        self._launch(DocumentWorker(self.snapshot, copy_args=args, parent=self), copying=True)

    def reject(self):
        if self._worker_running():
            self._worker.requestInterruption()
            self._close_later = True
            self.status.setText('Avbryter uten å publisere delvis indeks eller kopiering…')
            return
        super().reject()

    def closeEvent(self, event):
        if self._worker_running():
            self._worker.requestInterruption()
            self._close_later = True
            event.ignore()
            return
        super().closeEvent(event)


class AnalysisWorkspaceDialogV6(AnalysisWorkspaceDialogV5):
    """Preserve classic and A2-A5 Analyse; add an independent control route."""

    def __init__(self, snapshot, parent=None):
        super().__init__(snapshot, parent)
        self.setObjectName('dwm_analysis_v027_a6')
        self.controls_button = QPushButton(
            'Noark 5-kontroller → Velg nivå / Filformater / Dokumentkopiering', self)
        self.controls_button.setToolTip('Åpner selvstendig kontrollvisning med direkte nivåvalg '
                                        'og filobjekter fra DWM/Siegfried.')
        self.controls_button.clicked.connect(self._open_controls)
        self.layout().insertWidget(self.layout().count()-1, self.controls_button)

    def _open_controls(self):
        settings = getattr(getattr(self.parent(), 'api', None), 'settings', None)
        dialog = Noark5ControlWorkspace(self.snapshot, settings, self)
        dialog.exec()


def install_analysis_workspace_v6(window) -> bool:
    if not getattr(window, '_analysis_v027_a5_installed', False):
        return False
    window._analysis_dialog_class = AnalysisWorkspaceDialogV6
    window._analysis_v027_a6_installed = True
    return True
