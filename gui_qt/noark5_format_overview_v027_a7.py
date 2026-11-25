"""A7: PUID/category first, individual files only on explicit drill-down.

Retains A6's scope, policy, review, selected-copy and source safeguards.
The existing A5 object browser remains a separate sampling-oriented route.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QLabel,
    QListWidgetItem, QMessageBox, QPushButton, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.noark5_document_workbench_v027_a6 import (
    PSEUDO, format_annotations, format_policy_label, latest_assessment,
)
from app.noark5_format_overview_v027_a7 import (
    copy_with_history, export_history, file_page_seek, puid_overview,
)
from .noark5_document_workbench_v027_a6 import (
    AnalysisWorkspaceDialogV6, DocumentWorker, LEVELS, Noark5ControlWorkspace,
    _h,
)


class DocumentWorkerV7(DocumentWorker):
    """Copy through A6, then append Work-only A7 receipts; index path unchanged."""

    def run(self):
        try:
            if self.copy_args:
                result = copy_with_history(
                    self.snapshot, **self.copy_args,
                    cancelled=self.isInterruptionRequested,
                    progress=lambda n, total: self.progress.emit(n, total))
            else:
                from app.noark5_document_workbench_v027_a6 import build_document_index
                result = build_document_index(
                    self.snapshot, cancelled=self.isInterruptionRequested,
                    progress=lambda n: self.progress.emit(n, 0))
            self.success.emit(result)
        except Exception as exc:
            self.failure.emit(str(exc))


class Noark5ControlWorkspaceV7(Noark5ControlWorkspace):
    """One row per PUID. Existing a6 detail table is available on demand."""

    def __init__(self, snapshot, settings=None, parent=None):
        self._a7_ready = False
        self._format_mode = 'groups'
        self._a7_groups = ()
        self._group_page = 0
        self._group_size = 100
        self._group_rows = []
        self._rendering_groups = False
        self._file_puid = ''
        self._file_cursors = [0]
        self._file_page = 0
        self._file_next = False
        self._copy_result = None
        super().__init__(snapshot, settings, parent)
        self.setObjectName('dwm_noark5_controls_v027_a7')
        self.setWindowTitle('Analyse – Noark 5-kontroller / PUID-oversikt – ' + snapshot.job_id)
        self.resize(1500, 900)
        self._a7_ready = True

        outer = self.layout()
        navigation = QHBoxLayout()
        self.level_up = QPushButton('← Forrige Noark-nivå', self)
        self.level_up.clicked.connect(lambda: self._step_level(-1))
        navigation.addWidget(self.level_up)
        self.level_down = QPushButton('Neste Noark-nivå →', self)
        self.level_down.clicked.connect(lambda: self._step_level(1))
        navigation.addWidget(self.level_down)
        self.level_path = QLabel('', self)
        self.level_path.setWordWrap(True)
        navigation.addWidget(self.level_path, 1)
        outer.insertLayout(2, navigation)

        self.category = QComboBox(self)
        self.category.addItem('Alle MIME-grupper', '')
        self.category.currentIndexChanged.connect(self._category_changed)
        category_row = QHBoxLayout()
        category_row.addWidget(QLabel('Kategori / MIME-gruppe:', self))
        category_row.addWidget(self.category, 2)
        self.show_files = QPushButton('↓ Vis filer for valgt PUID', self)
        self.show_files.clicked.connect(self._drill_to_files)
        category_row.addWidget(self.show_files)
        self.to_groups = QPushButton('↑ Til PUID-grupper', self)
        self.to_groups.clicked.connect(self._back_to_groups)
        category_row.addWidget(self.to_groups)
        category_row.addStretch(1)
        outer.insertLayout(4, category_row)

        # Use one middle panel for both views, but keep the inherited A6 file
        # table and all its selection/review signals intact.
        middle_layout = self.files.parentWidget().layout()
        old_index = middle_layout.indexOf(self.files)
        middle_layout.removeWidget(self.files)
        self.view_stack = QStackedWidget(self)
        self.group_table = QTableWidget(0, 9, self.view_stack)
        self.group_table.setHorizontalHeaderLabels((
            'Velg', 'PUID', 'Kategori', 'MIME-gruppe', 'Filformat',
            'Filer', 'Kopier', 'Eksporter', 'Faglig vurdering'))
        self.group_table.verticalHeader().hide()
        self.group_table.setAlternatingRowColors(True)
        self.group_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.group_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.group_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        for col, width in enumerate((48, 105, 110, 140, 260, 80, 75, 75, 145)):
            self.group_table.setColumnWidth(col, width)
        self.group_table.setSortingEnabled(False)
        self.group_table.itemSelectionChanged.connect(self._selected_group)
        self.group_table.itemChanged.connect(self._toggle_group_choice)
        self.group_table.cellDoubleClicked.connect(self._group_double_clicked)
        self.view_stack.addWidget(self.group_table)
        self.view_stack.addWidget(self.files)
        middle_layout.insertWidget(max(0, old_index), self.view_stack, 1)
        self.files.setColumnCount(7)
        self.files.setHorizontalHeaderLabels((
            'PUID', 'Dokumentfil / relativ sti', 'Format', 'Bytes',
            'Arkivdel', 'Dokumentobjekt', 'Kopiert'))

        for caption in self.types.parentWidget().findChildren(QLabel):
            if caption.text().startswith('Filtyper'):
                caption.setText('Filtyper – avmerk PUID for visning og kopiering')
                break
        self.history_button = QPushButton('Kopihistorikk…', self)
        self.history_button.clicked.connect(self._show_copy_history)
        copy_row = outer.itemAt(outer.count() - 1).layout()
        if copy_row is not None:
            copy_row.insertWidget(max(0, copy_row.count() - 1), self.history_button)
        self.search.setPlaceholderText('Søk i PUID, format eller MIME-gruppe')
        self._shell()
        self._show_groups()

    def _step_level(self, delta):
        destination = self.level.currentIndex() + delta
        if 0 <= destination < self.level.count():
            self.level.setCurrentIndex(destination)

    def _update_nav(self):
        n = self.level.currentIndex()
        self.level_up.setEnabled(n > 0)
        self.level_down.setEnabled(0 <= n < self.level.count() - 1)
        label = self.level.currentText()
        self.level_path.setText('Nivå ' + str(n + 1) + ' av ' + str(self.level.count())
                                + ' · ' + label + ' · eller hopp direkte via Nivå-velgeren')

    def _shell(self):
        super()._shell()
        if not getattr(self, '_a7_ready', False):
            return
        at_files = self.level.currentData() == 'dokumentfil'
        self.splitter.setVisible(at_files)
        self.level_help.setVisible(not at_files)
        self.object_bridge.setVisible(not at_files)
        self.copy_flat.setEnabled(at_files and bool(self.meta))
        self.copy_button.setEnabled(at_files and bool(self.meta)
                                    and not self._worker_running())
        self.review_button.setEnabled(at_files and bool(self.meta))
        self.category.setVisible(at_files)
        self.show_files.setVisible(at_files)
        self.to_groups.setVisible(at_files)
        self.history_button.setVisible(at_files)
        self._update_nav()
        if not at_files:
            self._format_mode = 'groups'
            self.level_help.setHtml(
                '<h3>' + _h(self.level.currentText()) + '</h3>'
                '<p>Dette nivået er med i den gjennomgående Noark 5-navigasjonen. '
                'Det er foreløpig ikke en fullstendig krav-/resultatvisning for dette nivået.</p>'
                '<p>Eksisterende Analyse og a5-objektleseren brukes til faktiske '
                'objekter og kontrollresultater. Naviger videre med knappene '
                'eller hopp direkte til et annet nivå.</p>')
        else:
            self._update_page()

    def _category_changed(self, *_):
        self._group_page = 0
        self._format_mode = 'groups'
        self.search.clear()
        self._show_groups()

    def _refresh_groups(self):
        if not getattr(self, '_a7_ready', False):
            return super()._refresh_groups()
        if not self.meta or self._worker_running() or self.level.currentData() != 'dokumentfil':
            return
        try:
            result = puid_overview(self.snapshot, self.meta, part_id=self._part())
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))
            self._a7_groups = ()
            self.types.clear()
            self.group_table.setRowCount(0)
            return
        old = {self.types.item(i).data(Qt.ItemDataRole.UserRole):
               self.types.item(i).checkState() == Qt.CheckState.Checked
               for i in range(self.types.count())}
        self._a7_groups = result
        if not result and self._part():
            self.status.setText(
                'Ingen individuelt kildekoblede filer er dokumentert for valgt arkivdel. '
                'Dette betyr IKKE at arkivdelen mangler dokumentfiler. '
                'Velg Hele uttrekket for filene uten entydig arkivdelkobling.')
        self._groups = [dict(puid=r['puid'], name=r['format'], count=r['files'],
                             version=r['version']) for r in result]
        self._loading = True
        try:
            self.types.clear()
            for group in result:
                puid = group['puid']
                name = PSEUDO.get(puid, puid)
                label = name + ' · ' + str(group['files']) + ' filer'
                entry = QListWidgetItem(label)
                entry.setFlags(entry.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                entry.setCheckState(Qt.CheckState.Checked if old.get(puid, True)
                                    else Qt.CheckState.Unchecked)
                entry.setData(Qt.ItemDataRole.UserRole, puid)
                self.types.addItem(entry)
            prior = self.category.currentData()
            self.category.blockSignals(True)
            self.category.clear()
            self.category.addItem('Alle MIME-grupper', '')
            for label in sorted({r['group'] for r in result}):
                self.category.addItem(label, label)
            at = self.category.findData(prior)
            if at >= 0:
                self.category.setCurrentIndex(at)
            self.category.blockSignals(False)
        finally:
            self._loading = False
        if self._format_mode == 'files' and self._file_puid not in {r['puid'] for r in result}:
            self._format_mode = 'groups'
        self._update_page()

    def _update_page(self):
        if not getattr(self, '_a7_ready', False):
            return super()._update_page()
        if self.level.currentData() != 'dokumentfil' or not self.meta:
            return
        if self._format_mode == 'files':
            self._show_file_page()
        else:
            self._show_groups()

    def _filtered_groups(self):
        if not self.meta:
            return ()
        selected = set(self._selected_formats())
        category = str(self.category.currentData() or '')
        search = self.search.text().strip().casefold()
        return tuple(g for g in self._a7_groups
                     if g['puid'] in selected
                     and (not category or g['group'] == category)
                     and (not search or search in (' '.join((
                         g['puid'], g['group'], g['mime'], g['format'],
                         g['version'])).casefold())))

    def _show_groups(self):
        if not getattr(self, '_a7_ready', False) or not self.meta:
            return
        if self.level.currentData() != 'dokumentfil':
            return
        # Entering the summary must never populate the file-level widget.
        self.view_stack.setCurrentWidget(self.group_table)
        self.show_files.setEnabled(True)
        self.to_groups.setEnabled(False)
        filtered = self._filtered_groups()
        pages = max(1, (len(filtered) + self._group_size - 1) // self._group_size)
        self._group_page = min(self._group_page, pages - 1)
        start = self._group_page * self._group_size
        self._group_rows = list(filtered[start:start+self._group_size])
        selected_puid = self._preferred_puid
        checked_puids = {self.types.item(j).data(Qt.ItemDataRole.UserRole)
                         for j in range(self.types.count())
                         if self.types.item(j).checkState() == Qt.CheckState.Checked}
        self._rendering_groups = True
        try:
            self.group_table.setRowCount(len(self._group_rows))
            for i, g in enumerate(self._group_rows):
                values = (True, PSEUDO.get(g['puid'], g['puid']),
                          g['group'], g['mime'], g['format'] or 'Ukjent',
                          str(g['files']), str(g['copy_events']),
                          str(g['copy_exports']),
                          {'accepted': 'Faglig akseptert', 'deviation': 'Avvik',
                           'clarify': 'Til avklaring', '': 'Ikke vurdert'}.get(
                               self._assessment_cache.get(g['puid'], ''), 'Ukjent'))
                for col, value in enumerate(values):
                    item = QTableWidgetItem('' if col == 0 else str(value))
                    if col == 0:
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        checked = g['puid'] in checked_puids
                        item.setCheckState(Qt.CheckState.Checked if checked
                                           else Qt.CheckState.Unchecked)
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setData(Qt.ItemDataRole.UserRole, g['puid'])
                    self.group_table.setItem(i, col, item)
        finally:
            self._rendering_groups = False
        self.page_info.setText(
            f'{len(filtered)} PUID-grupper · side {self._group_page + 1} av {pages} · '
            f'{self.meta["files_total"]:,} filer i hele registeret'.replace(',', ' '))
        self.prev.setEnabled(self._group_page > 0)
        self.next.setEnabled(self._group_page + 1 < pages)
        self.search.setPlaceholderText('Søk i PUID, MIME-gruppe og filformat')
        chosen = next((i for i, g in enumerate(self._group_rows)
                       if g['puid'] == selected_puid), 0 if self._group_rows else -1)
        if chosen >= 0:
            self.group_table.selectRow(chosen)
        else:
            self._preferred_puid = ''
            self.details.setHtml('<p>Velg en PUID-gruppe.</p>')
        self._show_details()

    def _selected_group(self):
        if self._rendering_groups or self._format_mode == 'files':
            return
        idx = self.group_table.currentRow()
        if 0 <= idx < len(self._group_rows):
            self._preferred_puid = self._group_rows[idx]['puid']
            self._show_details()

    def _toggle_group_choice(self, changed):
        if self._rendering_groups or changed.column() != 0:
            return
        puid = changed.data(Qt.ItemDataRole.UserRole)
        self._loading = True
        try:
            for i in range(self.types.count()):
                item = self.types.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == puid:
                    item.setCheckState(changed.checkState())
                    break
        finally:
            self._loading = False
        QTimer.singleShot(0, self._show_groups)

    def _group_double_clicked(self, row, column):
        if column == 0:
            return
        if 0 <= row < len(self._group_rows):
            self._preferred_puid = self._group_rows[row]['puid']
            self._drill_to_files()

    def _drill_to_files(self):
        if not self.meta or self.level.currentData() != 'dokumentfil':
            return
        row = self.group_table.currentRow()
        if 0 <= row < len(self._group_rows):
            self._file_puid = self._group_rows[row]['puid']
        else:
            self._file_puid = self._preferred_puid
        if not self._file_puid:
            return
        self._format_mode = 'files'
        self._file_cursors = [0]
        self._file_page = 0
        self.search.clear()
        self._show_file_page()

    def _back_to_groups(self):
        self._format_mode = 'groups'
        self.search.clear()
        self._show_groups()

    def _show_file_page(self):
        if not self.meta or not self._file_puid:
            return
        try:
            result = file_page_seek(
                self.snapshot, self.meta, puid=self._file_puid,
                part_id=self._part(), search=self.search.text(),
                after_id=self._file_cursors[self._file_page], limit=100)
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))
            return
        self._rows = result['rows']
        self._file_next = result['has_next']
        self.files.blockSignals(True)
        try:
            self.files.setRowCount(len(self._rows))
            for i, record in enumerate(self._rows):
                values = (PSEUDO.get(record['puid'], record['puid']),
                          record['rel'], record['fmt'] or 'Ukjent',
                          record['size'], record['part_id'] or 'Ikke koblet',
                          record['doc_id'] or 'Ikke koblet',
                          ('Ja · ' + str(record['copies_recorded'])
                           if record['copies_recorded'] else 'Ikke registrert'))
                for c, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setToolTip(str(value))
                    self.files.setItem(i, c, item)
            if self._rows:
                self.files.selectRow(0)
        finally:
            self.files.blockSignals(False)
        self.view_stack.setCurrentWidget(self.files)
        self.show_files.setEnabled(False)
        self.to_groups.setEnabled(True)
        self.search.setPlaceholderText('Søk i filer under valgt PUID')
        self.page_info.setText('PUID ' + self._file_puid + ' · '
                               + str(len(self._rows)) + ' filer på side '
                               + str(self._file_page + 1)
                               + ' · sidevis indekssøk')
        self.prev.setEnabled(self._file_page > 0)
        self.next.setEnabled(self._file_next)
        self._selected_file_changed()

    def _step_page(self, delta):
        if not self._a7_ready:
            return super()._step_page(delta)
        if self._format_mode == 'groups':
            self._group_page = max(0, self._group_page + delta)
            self._show_groups()
        elif delta < 0 and self._file_page > 0:
            self._file_page -= 1
            self._show_file_page()
        elif delta > 0 and self._file_next and self._rows:
            self._file_cursors = self._file_cursors[:self._file_page+1]
            self._file_cursors.append(self._rows[-1]['id'])
            self._file_page += 1
            self._show_file_page()

    def _reset_page(self, *_):
        if not getattr(self, '_a7_ready', False):
            return super()._reset_page()
        if self._format_mode == 'files':
            self._file_cursors = [0]
            self._file_page = 0
        else:
            self._group_page = 0
        self._update_page()

    def _show_details(self):
        if not getattr(self, '_a7_ready', False):
            return super()._show_details()
        if self._format_mode == 'files':
            super()._show_details()
            row = self.files.currentRow()
            if 0 <= row < len(self._rows):
                copies = self._rows[row].get('copies_recorded', 0)
                cursor = self.details.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertHtml('<p><b>Kopihistorikk for filen:</b> '
                                  + (str(copies) + ' registrerte eksporter' if copies
                                     else 'Ingen eksport registrert fra a7') + '</p>')
            return
        puid = self._preferred_puid
        group = next((g for g in self._a7_groups if g['puid'] == puid), None)
        if not group:
            self.details.setHtml('<p>Velg en PUID-gruppe for formatvurdering.</p>')
            return
        try:
            label, explanation = self._policy(puid)
            notes = format_annotations(self.snapshot, self.meta, puid)
            current = latest_assessment(self.snapshot, self.meta, puid)
        except (OSError, ValueError) as exc:
            self.details.setHtml('<p>Kan ikke lese vurdering: ' + _h(exc) + '</p>')
            return
        html = '<h3>' + _h(PSEUDO.get(puid, puid)) + '</h3>'
        html += '<p><b>Filformat:</b> ' + _h(group['format'])
        html += '<br><b>Kategori:</b> ' + _h(group['group'])
        html += '<br><b>MIME-gruppe (veiledende):</b> ' + _h(group['mime'])
        html += '<br><b>Antall i valgt omfang:</b> ' + str(group['files']) + '</p>'
        html += '<p><b>Registrerte kopieringer fra a7:</b> ' + str(group['copy_events'])
        html += ' filer fordelt på ' + str(group['copy_exports']) + ' eksporter'
        html += '<br><b>Sist kopiert:</b> ' + _h(group['last_copy']) + '</p>'
        html += '<p><b>Valgt formatliste:</b> ' + _h(self.authority.currentText())
        html += '<br><b>Regel-/RAF-vurdering:</b> ' + _h(label)
        html += '<br>' + _h(explanation) + '</p>'
        html += '<p><b>Faglig vurdering:</b> ' + _h({
            'accepted': 'Akseptert i dette uttrekket – ikke formelt godkjent',
            'deviation': 'Avvik dokumentert',
            'clarify': 'Krever avklaring',
            '': 'Ingen faglig vurdering',
        }.get(current, 'Ukjent')) + '</p>'
        html += '<h4>Historiserte merknader</h4>'
        if notes:
            for note in notes[-20:]:
                actor = note.get('user') or {}
                html += ('<p>' + _h(note.get('created_at')) + ' · '
                         + _h(actor.get('name') or actor.get('username'))
                         + ' · ' + _h(note.get('annotation_type')) + '<br>'
                         + _h(note.get('text')) + '</p>')
        else:
            html += '<p>Ingen kommentarer registrert.</p>'
        html += ('<p><i>MIME er bare en veiledende gruppe utledet av formatnavnet. '
                 'Det er ikke et nytt identifikasjonsbevis. '
                 'Tidligere a6-eksporter er ikke automatisk importert til historikken.</i></p>')
        self.details.setHtml(html)

    def _launch(self, worker, *, copying):
        if copying:
            # Replace only the copy worker, preserving A6's fully-verified copy.
            worker = DocumentWorkerV7(self.snapshot, copy_args=worker.copy_args, parent=self)
        return super()._launch(worker, copying=copying)

    def _progress(self, done, total):
        if self._copy_mode and total < 0:
            self.status.setText('Registrerer kopihistorikk: '
                                + str(done) + ' av ' + str(-total) + ' filer…')
        else:
            super()._progress(done, total)

    def _completed(self, value):
        if not self._copy_mode:
            return super()._completed(value)
        self._copy_result = value
        self.status.setText('Kopiert ' + str(value['files_copied']) + ' filer til ' + value['path'])
        if value.get('history_state') != 'recorded':
            QMessageBox.warning(
                self, 'Kopiering ferdig – historikk må kontrolleres',
                'Filene er kopiert og verifisert til:\n' + value['path']
                + '\n\nKopihistorikk ble ikke registrert i Work: '
                + str(value.get('history_warning') or 'ukjent feil'))
        else:
            QMessageBox.information(
                self, 'Kopiering og historikk fullført',
                str(value['files_copied']) + ' filer kopiert og registrert i Work.\n\n'
                + 'Mål: ' + value['path'] + '\nManifest: ' + value['manifest'])

    def _finished(self):
        was_copy = self._copy_mode
        super()._finished()
        if was_copy and self.meta and not self._close_later:
            self._refresh_groups()

    def _show_copy_history(self):
        if not self.meta:
            return
        try:
            records = export_history(self.snapshot, self.meta)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Kopihistorikk', str(exc))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Kopihistorikk – ' + self.snapshot.job_id)
        dialog.resize(1050, 560)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('Registrerte, fullførte kopieringer fra a7. '
                                'Eldre a6-eksporter inngår ikke automatisk.', dialog))
        table = QTableWidget(len(records), 6, dialog)
        table.setHorizontalHeaderLabels(('Dato (UTC)', 'Filer', 'PUID-grupper',
                                         'Struktur', 'Arkivdel', 'Målmappe'))
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().hide()
        table.setColumnWidth(0, 185)
        table.setColumnWidth(1, 80)
        table.setColumnWidth(2, 105)
        table.setColumnWidth(3, 120)
        table.setColumnWidth(4, 115)
        table.horizontalHeader().setStretchLastSection(True)
        for i, record in enumerate(records):
            for col, text in enumerate((record['date'], record['files'],
                                        record['puid_count'], record['layout'],
                                        record['part_id'] or 'Hele uttrekket', record['output'])):
                table.setItem(i, col, QTableWidgetItem(str(text)))
        layout.addWidget(table, 1)
        finish = QPushButton('Lukk', dialog)
        finish.clicked.connect(dialog.accept)
        layout.addWidget(finish)
        dialog.exec()


class AnalysisWorkspaceDialogV7(AnalysisWorkspaceDialogV6):
    """Add PUID-first control route without replacing A5's sampling view."""

    def __init__(self, snapshot, parent=None):
        super().__init__(snapshot, parent)
        self.setObjectName('dwm_analysis_v027_a7')
        self.controls_button.setText(
            'Noark 5-kontroller → PUID-grupper / Dokumentfiler / Kopihistorikk')

    def _open_controls(self):
        settings = getattr(getattr(self.parent(), 'api', None), 'settings', None)
        Noark5ControlWorkspaceV7(self.snapshot, settings, self).exec()


def install_analysis_workspace_v7(window) -> bool:
    if not getattr(window, '_analysis_v027_a6_installed', False):
        return False
    window._analysis_dialog_class = AnalysisWorkspaceDialogV7
    window._analysis_v027_a7_installed = True
    return True
