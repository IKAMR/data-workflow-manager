"""A8 PUID-first controls: sortable selector, global group sorts and saved copy output.

This extends A7's source-bound PUID index, file detail and copy receipt ledger.
No Source operation, Noark analysis, or older Analyse view is replaced.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QSignalBlocker, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
)

from app.noark5_document_workbench_v027_a6 import PSEUDO
from app.noark5_format_overview_v027_a7 import puid_overview
from app.noark5_format_sort_v027_a8 import (
    LEFT_COLUMNS, copy_structure, next_sort, sorted_puid_groups,
)
from .noark5_document_workbench_v027_a6 import DocumentWorker, _h
from .noark5_format_overview_v027_a7 import (
    AnalysisWorkspaceDialogV7, Noark5ControlWorkspaceV7,
)


_SETTINGS_PREFIX = 'analysis/v027_a8/'


class Noark5ControlWorkspaceV8(Noark5ControlWorkspaceV7):
    """A small, PUID-based left table; sort every group before paging.

    The a7 file-level reader still seeks across the verified SQLite index.
    Sorting all individual file records in the GUI would be misleading for
    million-file extractions; only PUID-group totals are globally sorted here.
    """

    def __init__(self, snapshot, settings=None, parent=None):
        self._a8_ready = False
        self._a8_choices: dict[str, bool] = {}
        self._a8_left_rows: tuple[dict, ...] = ()
        self._a8_left_sort = (1, False)  # PUID ascending
        self._a8_main_sort = (5, True)   # Total files descending
        self._a8_painting = False
        super().__init__(snapshot, settings, parent)
        self.setObjectName('dwm_noark5_controls_v027_a8')
        self.setWindowTitle('Analyse – Noark 5-kontroller / PUID-oversikt – ' + snapshot.job_id)

        # Replace only the A7 selection list; the central group/file stack,
        # A7 receipt logic and all other navigation are unchanged.
        old = self.types
        host = old.parentWidget()
        layout = host.layout()
        position = layout.indexOf(old)
        layout.removeWidget(old)
        old.hide()
        old.deleteLater()
        self.types = QTableWidget(0, len(LEFT_COLUMNS), host)
        self.types.setHorizontalHeaderLabels(LEFT_COLUMNS)
        self.types.verticalHeader().hide()
        self.types.setAlternatingRowColors(True)
        self.types.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.types.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.types.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.types.setSortingEnabled(False)
        self.types.horizontalHeader().setSectionsClickable(True)
        self.types.horizontalHeader().setSortIndicatorShown(True)
        self.types.horizontalHeader().setSortIndicator(1, Qt.SortOrder.AscendingOrder)
        self.types.horizontalHeader().sectionClicked.connect(self._sort_left)
        for index, width in enumerate((48, 94, 92, 115, 56)):
            self.types.setColumnWidth(index, width)
        self.types.itemChanged.connect(self._left_checked)
        self.types.itemSelectionChanged.connect(self._left_selected)
        layout.insertWidget(max(0, position), self.types, 1)
        host.setMinimumWidth(390)
        self.splitter.setSizes([425, 730, 345])

        # A7's original group table was deliberately not sorted because the
        # display is paginated. A8 sorts ALL PUID groups first, then pages.
        header = self.group_table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(5, Qt.SortOrder.DescendingOrder)
        header.sectionClicked.connect(self._sort_main)
        self.group_table.setSortingEnabled(False)

        self._copy_settings = QSettings('IKAMR', 'DWM-Qt')
        raw_structure = self._copy_settings.value(_SETTINGS_PREFIX + 'structure', 'puid')
        structure = copy_structure(raw_structure)
        position = self.copy_flat.findData(structure)
        self.copy_flat.setCurrentIndex(max(0, position))
        self.copy_flat.currentIndexChanged.connect(self._save_copy_structure)
        self._output_root = str(self._copy_settings.value(
            _SETTINGS_PREFIX + 'output_root', '') or '').strip()
        output_line = QHBoxLayout()
        output_line.addWidget(QLabel('Outputmappe:', self))
        self.output_path = QLineEdit(self)
        self.output_path.setReadOnly(True)
        self.output_path.setPlaceholderText('Ikke valgt – blir spurt ved første kopiering')
        self.output_path.setToolTip('Valgt outputområde lagres på denne PC-en. '
                                    'DWM lager en ny DWM-filutvalg-mappe for hver eksport.')
        self.output_path.setText(self._output_root)
        output_line.addWidget(self.output_path, 1)
        self.choose_output = QPushButton('Velg outputmappe…', self)
        self.choose_output.clicked.connect(self._choose_output)
        output_line.addWidget(self.choose_output)
        self.layout().insertLayout(self.layout().count() - 1, output_line)

        self._a8_ready = True
        if self.meta:
            self._refresh_groups()

    def _sort_left(self, column: int):
        self._a8_left_sort = next_sort(self._a8_left_sort, column, selector=True)
        self.types.horizontalHeader().setSortIndicator(
            column, Qt.SortOrder.DescendingOrder if self._a8_left_sort[1]
            else Qt.SortOrder.AscendingOrder)
        self._render_left()

    def _sort_main(self, column: int):
        self._a8_main_sort = next_sort(self._a8_main_sort, column)
        self.group_table.horizontalHeader().setSortIndicator(
            column, Qt.SortOrder.DescendingOrder if self._a8_main_sort[1]
            else Qt.SortOrder.AscendingOrder)
        self._group_page = 0
        self._show_groups()

    def _render_left(self):
        if not self._a8_ready:
            return
        prior = self._preferred_puid
        self._a8_left_rows = sorted_puid_groups(
            self._a7_groups, column=self._a8_left_sort[0],
            descending=self._a8_left_sort[1], selector=True,
            checked=self._a8_choices)
        self._a8_painting = True
        try:
            with QSignalBlocker(self.types):
                self.types.setRowCount(len(self._a8_left_rows))
                for row_num, group in enumerate(self._a8_left_rows):
                    puid = group['puid']
                    checks = QTableWidgetItem('')
                    checks.setFlags(checks.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    checks.setCheckState(Qt.CheckState.Checked if self._a8_choices.get(puid, True)
                                         else Qt.CheckState.Unchecked)
                    checks.setData(Qt.ItemDataRole.UserRole, puid)
                    self.types.setItem(row_num, 0, checks)
                    values = (PSEUDO.get(puid, puid), group['group'],
                              group['mime'], str(group['files']))
                    for col, value in enumerate(values, 1):
                        item = QTableWidgetItem(str(value))
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        item.setToolTip(str(value))
                        item.setData(Qt.ItemDataRole.UserRole, puid)
                        self.types.setItem(row_num, col, item)
                index = next((i for i, g in enumerate(self._a8_left_rows)
                              if g['puid'] == prior), -1)
                if index >= 0:
                    self.types.selectRow(index)
                elif self._a8_left_rows:
                    self.types.selectRow(0)
        finally:
            self._a8_painting = False

    def _left_checked(self, item):
        if self._a8_painting or item.column() != 0:
            return
        puid = str(item.data(Qt.ItemDataRole.UserRole) or '')
        if puid:
            self._a8_choices[puid] = item.checkState() == Qt.CheckState.Checked
        self._apply_filter()

    def _left_selected(self):
        if self._a8_painting or self._format_mode == 'files':
            return
        idx = self.types.currentRow()
        if 0 <= idx < len(self._a8_left_rows):
            self._preferred_puid = self._a8_left_rows[idx]['puid']
            self._show_details()

    def _refresh_groups(self):
        if not self._a8_ready:
            return super()._refresh_groups()
        if (not self.meta or self._worker_running()
                or self.level.currentData() != 'dokumentfil'):
            return
        try:
            result = puid_overview(self.snapshot, self.meta, part_id=self._part())
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))
            self._a7_groups = ()
            self._groups = []
            self.types.setRowCount(0)
            self.group_table.setRowCount(0)
            return
        self._a7_groups = result
        if not result and self._part():
            self.status.setText(
                'Ingen individuelt kildekoblede filer for valgt arkivdel. '
                'Det betyr ikke at arkivdelen mangler dokumentfiler.')
        self._groups = [dict(puid=g['puid'], name=g['format'],
                             count=g['files'], version=g['version']) for g in result]
        for group in result:
            self._a8_choices.setdefault(group['puid'], True)
        prior = self.category.currentData()
        with QSignalBlocker(self.category):
            self.category.clear()
            self.category.addItem('Alle MIME-grupper', '')
            for label in sorted({r['group'] for r in result}):
                self.category.addItem(label, label)
            idx = self.category.findData(prior)
            if idx >= 0:
                self.category.setCurrentIndex(idx)
        if (self._format_mode == 'files'
                and self._file_puid not in {g['puid'] for g in result}):
            self._format_mode = 'groups'
        self._render_left()
        self._update_page()

    def _mark_all(self, checked):
        if not self._a8_ready:
            return super()._mark_all(checked)
        for group in self._a7_groups:
            self._a8_choices[group['puid']] = bool(checked)
        self._render_left()
        self._apply_filter()

    def _selected_formats(self):
        if not self._a8_ready:
            return super()._selected_formats()
        if not self.meta:
            return ()
        status = self.status_filter.currentData()
        chosen = []
        for group in self._a7_groups:
            puid = group['puid']
            if not self._a8_choices.get(puid, True):
                continue
            review = self._assessment_cache.get(puid, '')
            if status in ('deviation', 'accepted', 'clarify', 'unreviewed'):
                if status == 'unreviewed' and review:
                    continue
                if status != 'unreviewed' and review != status:
                    continue
            elif status == 'unknown' and puid not in PSEUDO:
                continue
            elif status == 'profile':
                label, _note = self._policy(puid)
                if (not label.startswith('Akseptert i valgt profil')
                        and not label.startswith('Arkade: Gyldig arkivformat')):
                    continue
            chosen.append(puid)
        return tuple(chosen)

    def _show_groups(self):
        if not self._a8_ready:
            return super()._show_groups()
        if not self.meta or self.level.currentData() != 'dokumentfil':
            return
        self.view_stack.setCurrentWidget(self.group_table)
        self.show_files.setEnabled(True)
        self.to_groups.setEnabled(False)
        visible = sorted_puid_groups(
            self._filtered_groups(), column=self._a8_main_sort[0],
            descending=self._a8_main_sort[1], checked=self._a8_choices,
            assessments=self._assessment_cache)
        pages = max(1, (len(visible) + self._group_size - 1) // self._group_size)
        self._group_page = min(self._group_page, pages - 1)
        start = self._group_page * self._group_size
        self._group_rows = list(visible[start:start + self._group_size])
        selected_puid = self._preferred_puid
        self._rendering_groups = True
        try:
            with QSignalBlocker(self.group_table):
                self.group_table.setRowCount(len(self._group_rows))
                for i, group in enumerate(self._group_rows):
                    puid = group['puid']
                    values = (
                        '', PSEUDO.get(puid, puid), group['group'],
                        group['mime'], group['format'] or 'Ukjent',
                        str(group['files']), str(group['copy_events']),
                        str(group['copy_exports']),
                        {'accepted': 'Faglig akseptert', 'deviation': 'Avvik',
                         'clarify': 'Til avklaring', '': 'Ikke vurdert'}.get(
                            self._assessment_cache.get(puid, ''), 'Ukjent'))
                    for col, value in enumerate(values):
                        item = QTableWidgetItem(str(value))
                        if col == 0:
                            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                            item.setCheckState(Qt.CheckState.Checked if self._a8_choices.get(puid, True)
                                               else Qt.CheckState.Unchecked)
                        else:
                            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        item.setData(Qt.ItemDataRole.UserRole, puid)
                        item.setToolTip(str(value))
                        self.group_table.setItem(i, col, item)
                index = next((j for j, g in enumerate(self._group_rows)
                              if g['puid'] == selected_puid), -1)
                if index >= 0:
                    self.group_table.selectRow(index)
                elif self._group_rows:
                    self.group_table.selectRow(0)
        finally:
            self._rendering_groups = False
        self.page_info.setText(
            f'{len(visible)} PUID-grupper · side {self._group_page + 1} av {pages} · '
            f'{self.meta["files_total"]:,} filer i hele registeret'.replace(',', ' '))
        self.prev.setEnabled(self._group_page > 0)
        self.next.setEnabled(self._group_page + 1 < pages)
        self.search.setPlaceholderText('Søk i PUID, MIME-gruppe og filformat')
        if self._group_rows:
            self._selected_group()
        else:
            self._preferred_puid = ''
            self.details.setHtml('<p>Ingen valgte PUID-grupper samsvarer med filteret.</p>')

    def _toggle_group_choice(self, changed):
        if not self._a8_ready:
            return super()._toggle_group_choice(changed)
        if self._rendering_groups or changed.column() != 0:
            return
        puid = str(changed.data(Qt.ItemDataRole.UserRole) or '')
        if puid:
            self._a8_choices[puid] = changed.checkState() == Qt.CheckState.Checked
        self._render_left()
        QTimer.singleShot(0, self._show_groups)

    def _save_copy_structure(self, *_):
        if not self._a8_ready:
            return
        self._copy_settings.setValue(
            _SETTINGS_PREFIX + 'structure', copy_structure(self.copy_flat.currentData()))
        self._copy_settings.sync()

    def _choose_output(self):
        selected = QFileDialog.getExistingDirectory(
            self, 'Velg fast outputområde for dokumentkopier', self._output_root)
        if not selected:
            return False
        self._output_root = selected
        self.output_path.setText(selected)
        self._copy_settings.setValue(_SETTINGS_PREFIX + 'output_root', selected)
        self._copy_settings.sync()
        return True

    def _copy_selected(self):
        if not self._a8_ready:
            return super()._copy_selected()
        if self._worker_running() or not self.meta:
            return
        if self._format_mode == 'files':
            selected = (self._file_puid,) if self._file_puid in self._selected_formats() else ()
        else:
            selected = tuple(group['puid'] for group in self._filtered_groups())
        if not selected:
            QMessageBox.information(self, 'Filkopiering', 'Merk minst én PUID-gruppe for kopiering.')
            return
        if not self._output_root or not Path(self._output_root).is_dir():
            QMessageBox.information(
                self, 'Velg outputområde',
                'Velg en outputmappe første gang. DWM husker den på denne PC-en. '
                'PUID-undermapper er anbefalt og valgt som standard.')
            if not self._choose_output():
                return
        total = sum(row['count'] for row in self._groups if row['puid'] in selected)
        structure = copy_structure(self.copy_flat.currentData())
        layout = 'PUID-undermapper (anbefalt)' if structure == 'puid' else 'Flat mappe'
        response = QMessageBox.question(
            self, 'Bekreft kopiering',
            f'Kopiere {total} filer fra {len(selected)} filtyper?\n\n'
            f'Outputmappe: {self._output_root}\n'
            f'Struktur: {layout}\n\n'
            'DWM kopierer alle filer innen hver valgt PUID (ikke bare filene på skjermsiden). '
            'Det lages en ny DWM-filutvalg-undermappe med sjekksumverifikasjon '
            'og eksporthistorikk i Work. Source endres ikke. Fortsette?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if response != QMessageBox.StandardButton.Yes:
            return
        args = {'meta': self.meta, 'selected_puids': selected,
                'destination': self._output_root, 'structure': structure,
                'part_id': self._part()}
        self._launch(DocumentWorker(self.snapshot, copy_args=args, parent=self), copying=True)


class AnalysisWorkspaceDialogV8(AnalysisWorkspaceDialogV7):
    """Add the A8 PUID selection and output preferences without changing A7."""

    def __init__(self, snapshot, parent=None):
        super().__init__(snapshot, parent)
        self.setObjectName('dwm_analysis_v027_a8')
        self.controls_button.setText(
            'Noark 5-kontroller → PUID-grupper / sortering / kopiering')

    def _open_controls(self):
        settings = getattr(getattr(self.parent(), 'api', None), 'settings', None)
        Noark5ControlWorkspaceV8(self.snapshot, settings, self).exec()


def install_analysis_workspace_v8(window) -> bool:
    if not getattr(window, '_analysis_v027_a7_installed', False):
        return False
    window._analysis_dialog_class = AnalysisWorkspaceDialogV8
    window._analysis_v027_a8_installed = True
    return True
