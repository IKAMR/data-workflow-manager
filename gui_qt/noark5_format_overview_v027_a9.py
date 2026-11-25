"""A9: explicit source-policy column and reversible compact PUID view.

A5 object inspection and A6/A7 source-bound file/copy mechanics remain intact.
The selected-format result belongs to the selected policy, not to the human
professional review, which retains its separate column and Work ledger.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSettings, QSignalBlocker
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout,
    QTableWidgetItem,
)

from app.noark5_document_workbench_v027_a6 import PSEUDO
from app.noark5_format_presentation_v027_a9 import (
    MAIN_COLUMNS_A9, compact_preference, format_rule_label,
    next_a9_sort, professional_label, sorted_a9_groups,
)
from .noark5_format_overview_v027_a8 import (
    AnalysisWorkspaceDialogV8, Noark5ControlWorkspaceV8,
)


_COMPACT_KEY = 'analysis/v027_a9/compact'


class Noark5ControlWorkspaceV9(Noark5ControlWorkspaceV8):
    """All PUIDs first, detailed files on demand; compact view is reversible."""

    def __init__(self, snapshot, settings=None, parent=None):
        self._a9_ready = False
        self._a9_compact = False
        self._a9_expanded_sizes = [425, 730, 345]
        super().__init__(snapshot, settings, parent)
        self.setObjectName('dwm_noark5_controls_v027_a9')
        self.setWindowTitle('Analyse – Noark 5-kontroller / PUID-oversikt – ' + snapshot.job_id)

        # Insert the actual selected-policy interpretation directly before
        # independent professional review. The A8 sort is still initialised
        # with 9 columns; all A9 sort indices are mapped separately below.
        self.group_table.setColumnCount(len(MAIN_COLUMNS_A9))
        self.group_table.setHorizontalHeaderLabels(MAIN_COLUMNS_A9)
        for index, width in enumerate((48, 110, 105, 138, 250,
                                       70, 70, 73, 210, 155)):
            self.group_table.setColumnWidth(index, width)
        self.group_table.horizontalHeaderItem(8).setToolTip(
            'Resultat fra formatlisten valgt øverst (Setup som standard). '
            'Treff i listen er ikke faglig eller formell depotgodkjenning.')
        self.group_table.horizontalHeaderItem(9).setToolTip(
            'Selvstendig, historisert faglig vurdering i Work – aldri automatisk utledet av formatlisten.')

        # A permanent toolbar remains accessible in MIN mode when the two
        # auxiliary panes are hidden. The old left-only actions are disabled
        # visually so there are no duplicated "Merk alle" buttons.
        left = self.types.parentWidget()
        left_buttons = left.layout().itemAt(1).layout()
        if left_buttons is not None:
            for i in range(left_buttons.count()):
                widget = left_buttons.itemAt(i).widget()
                if widget is not None:
                    widget.hide()
        bar = QHBoxLayout()
        self.a9_all = QPushButton('Merk alle', self)
        self.a9_all.clicked.connect(lambda: self._mark_all(True))
        bar.addWidget(self.a9_all)
        self.a9_none = QPushButton('Fjern alle', self)
        self.a9_none.clicked.connect(lambda: self._mark_all(False))
        bar.addWidget(self.a9_none)
        self.a9_compact_button = QPushButton('MIN visning', self)
        self.a9_compact_button.setToolTip(
            'MIN: skjul PUID-valgtabell og detaljpanel, behold hovedtabellen. '
            'MAX: gjenopprett alle tre panelene.')
        self.a9_compact_button.clicked.connect(self._toggle_compact)
        bar.addWidget(self.a9_compact_button)
        self.a9_details = QPushButton('Detaljer…', self)
        self.a9_details.clicked.connect(self._open_compact_details)
        bar.addWidget(self.a9_details)
        self.a9_review = QPushButton('Faglig vurdering…', self)
        self.a9_review.clicked.connect(self._edit_review)
        bar.addWidget(self.a9_review)
        bar.addStretch(1)
        self.layout().insertLayout(self.layout().indexOf(self.splitter), bar)

        self._a9_settings = QSettings('IKAMR', 'DWM-Qt')
        self._a9_ready = True
        initial = compact_preference(self._a9_settings.value(_COMPACT_KEY, False))
        self._set_compact(initial, persist=False)
        if self.meta:
            self._show_groups()

    def _sort_main(self, column: int):
        if not self._a9_ready:
            return super()._sort_main(column)
        self._a8_main_sort = next_a9_sort(self._a8_main_sort, column)
        self.group_table.horizontalHeader().setSortIndicator(
            column, (Qt.SortOrder.DescendingOrder if self._a8_main_sort[1]
                     else Qt.SortOrder.AscendingOrder))
        self._group_page = 0
        self._show_groups()

    def _policy_results(self, groups):
        labels, explanations = {}, {}
        for group in groups:
            puid = group['puid']
            try:
                label, explanation = self._policy(puid)
            except (ValueError, OSError) as exc:
                label, explanation = ('Vurdering utilgjengelig', str(exc))
            labels[puid] = format_rule_label(label)
            explanations[puid] = str(explanation or '')
        return labels, explanations

    def _show_groups(self):
        if not self._a9_ready:
            return super()._show_groups()
        if not self.meta or self.level.currentData() != 'dokumentfil':
            return
        self.view_stack.setCurrentWidget(self.group_table)
        self.show_files.setEnabled(True)
        self.to_groups.setEnabled(False)
        filtered = self._filtered_groups()
        policy_labels, policy_notes = self._policy_results(filtered)
        visible = sorted_a9_groups(
            filtered, column=self._a8_main_sort[0],
            descending=self._a8_main_sort[1], checked=self._a8_choices,
            assessments=self._assessment_cache, policy_labels=policy_labels)
        pages = max(1, (len(visible) + self._group_size - 1) // self._group_size)
        self._group_page = min(self._group_page, pages - 1)
        start = self._group_page * self._group_size
        self._group_rows = list(visible[start:start + self._group_size])
        selected = self._preferred_puid
        self._rendering_groups = True
        try:
            with QSignalBlocker(self.group_table):
                self.group_table.setRowCount(len(self._group_rows))
                for row, group in enumerate(self._group_rows):
                    puid = group['puid']
                    values = (
                        '', PSEUDO.get(puid, puid), group['group'], group['mime'],
                        group['format'] or 'Ukjent', str(group['files']),
                        str(group['copy_events']), str(group['copy_exports']),
                        policy_labels[puid],
                        professional_label(self._assessment_cache.get(puid, '')),
                    )
                    for col, value in enumerate(values):
                        cell = QTableWidgetItem(str(value))
                        if col == 0:
                            cell.setFlags(cell.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                            cell.setCheckState(
                                Qt.CheckState.Checked if self._a8_choices.get(puid, True)
                                else Qt.CheckState.Unchecked)
                        else:
                            cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        cell.setData(Qt.ItemDataRole.UserRole, puid)
                        cell.setToolTip(
                            ('Formatvurdering – ' + self.authority.currentText() + '\n'
                             + policy_labels[puid] + '\n' + policy_notes[puid])
                            if col == 8 else str(value))
                        self.group_table.setItem(row, col, cell)
                index = next((i for i, group in enumerate(self._group_rows)
                              if group['puid'] == selected), -1)
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

    def _shell(self):
        super()._shell()
        if not self._a9_ready:
            return
        is_document = self.level.currentData() == 'dokumentfil'
        for button in (self.a9_all, self.a9_none, self.a9_compact_button):
            button.setVisible(is_document)
        self.a9_details.setVisible(is_document and self._a9_compact)
        self.a9_review.setVisible(is_document and self._a9_compact)

    def _toggle_compact(self):
        self._set_compact(not self._a9_compact)

    def _set_compact(self, compact: bool, *, persist: bool = True):
        compact = bool(compact)
        if compact and not self._a9_compact:
            sizes = self.splitter.sizes()
            if len(sizes) == 3 and all(size > 0 for size in sizes):
                self._a9_expanded_sizes = sizes
        self._a9_compact = compact
        # Keep the middle group/file stack always visible. In MIN mode the
        # user can still check/uncheck rows in the main PUID table, use the
        # all/none actions, open details, and register a professional review.
        self.splitter.widget(0).setVisible(not compact)
        self.splitter.widget(2).setVisible(not compact)
        self.splitter.widget(1).setVisible(True)
        if not compact:
            prior = self._a9_expanded_sizes
            if len(prior) == 3 and all(size > 0 for size in prior):
                self.splitter.setSizes(prior)
        self.a9_compact_button.setText('MAX visning' if compact else 'MIN visning')
        self.a9_details.setVisible(compact and self.level.currentData() == 'dokumentfil')
        self.a9_review.setVisible(compact and self.level.currentData() == 'dokumentfil')
        if persist:
            self._a9_settings.setValue(_COMPACT_KEY, compact)
            self._a9_settings.sync()

    def _open_compact_details(self):
        if not self.meta:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('PUID – formatvurdering og evidens')
        dialog.resize(770, 590)
        layout = QVBoxLayout(dialog)
        details = QTextBrowser(dialog)
        details.setOpenExternalLinks(False)
        details.setHtml(self.details.toHtml())
        layout.addWidget(details, 1)
        controls = QHBoxLayout()
        review = QPushButton('Faglig vurdering / merknad…', dialog)
        def assess():
            self._edit_review()
            details.setHtml(self.details.toHtml())
        review.clicked.connect(assess)
        controls.addWidget(review)
        controls.addStretch(1)
        close = QPushButton('Lukk', dialog)
        close.clicked.connect(dialog.accept)
        controls.addWidget(close)
        layout.addLayout(controls)
        dialog.exec()


class AnalysisWorkspaceDialogV9(AnalysisWorkspaceDialogV8):
    """Expose A9 only in the new Analyse surface, preserving old routes."""

    def __init__(self, snapshot, parent=None):
        super().__init__(snapshot, parent)
        self.setObjectName('dwm_analysis_v027_a9')
        self.controls_button.setText(
            'Noark 5-kontroller → PUID / Formatvurdering / MIN/MAX visning')

    def _open_controls(self):
        settings = getattr(getattr(self.parent(), 'api', None), 'settings', None)
        Noark5ControlWorkspaceV9(self.snapshot, settings, self).exec()


def install_analysis_workspace_v9(window) -> bool:
    if not getattr(window, '_analysis_v027_a8_installed', False):
        return False
    window._analysis_dialog_class = AnalysisWorkspaceDialogV9
    window._analysis_v027_a9_installed = True
    return True
