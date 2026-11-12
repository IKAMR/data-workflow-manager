"""Separate Siegfried results page; never merge file counts with Arkade PRONOM."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QSplitter, QTextBrowser, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.format_policy_v0110_a4 import evaluate_puid
from app.result_display_v0110_a5 import readable_html
from app.siegfried_results_v0111_a3 import list_siegfried_runs
from .result_center_v0111_a2 import ResultCenterWindow as _PriorResultCenter


class ResultCenterWindow(_PriorResultCenter):
    """Append one independent evidence tab, preserving all 13 existing tabs."""

    def __init__(self, *args, **kwargs):
        self._sf_ready = False
        super().__init__(*args, **kwargs)
        self._sf_build_page()
        self._sf_ready = True
        self._sf_refresh()
        self.format_policy_combo.currentIndexChanged.connect(self._sf_refresh)

    def _sf_build_page(self):
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 9, 8, 8)
        layout.setSpacing(8)
        note = QLabel('Selvstendig Siegfried/PRONOM. Kilde og filantall holdes atskilt fra Arkade 5.')
        note.setWordWrap(True)
        layout.addWidget(note)
        choose = QHBoxLayout()
        choose.addWidget(QLabel('Kjøring:'))
        self.sf_history = QComboBox(page)
        self.sf_history.currentIndexChanged.connect(self._sf_selected)
        choose.addWidget(self.sf_history, 1)
        layout.addLayout(choose)
        self.sf_summary = QLabel('Ingen Siegfried-resultater registrert.')
        self.sf_summary.setWordWrap(True)
        layout.addWidget(self.sf_summary)
        self.sf_splitter = QSplitter(Qt.Orientation.Horizontal, page)
        self.sf_table = QTreeWidget(self.sf_splitter)
        self.sf_table.setRootIsDecorated(False)
        self.sf_table.setAlternatingRowColors(True)
        self.sf_table.setHeaderLabels(('PUID', 'Filtype', 'Versjon', 'Antall', 'DWM-vurdering'))
        self.sf_table.setSortingEnabled(True)
        self.sf_table.header().setStretchLastSection(True)
        self.sf_table.setColumnWidth(0, 112)
        self.sf_table.setColumnWidth(1, 270)
        self.sf_table.setColumnWidth(2, 75)
        self.sf_table.setColumnWidth(3, 75)
        self.sf_details = QTextBrowser(self.sf_splitter)
        self.sf_details.setOpenExternalLinks(False)
        self.sf_splitter.setStretchFactor(0, 3)
        self.sf_splitter.setStretchFactor(1, 2)
        self.sf_table.currentItemChanged.connect(self._sf_show_detail)
        layout.addWidget(self.sf_splitter, 1)
        self.tabs.addTab(page, 'Siegfried')
        self._sf_page = page
        self._sf_runs = []

    def refresh(self):
        super().refresh()
        if getattr(self, '_sf_ready', False):
            self._sf_refresh()

    def _sf_refresh(self, _ignored=None):
        if not getattr(self, '_sf_ready', False):
            return
        previous = self.sf_history.currentData()
        runs = []
        for shot in getattr(self, '_snapshots', ()):
            for item in list_siegfried_runs(shot.job.work):
                item['job_name'] = shot.job.name
                runs.append(item)
        self._sf_runs = runs
        self.sf_history.blockSignals(True)
        try:
            self.sf_history.clear()
            for i, item in enumerate(runs):
                self.sf_history.addItem(item['job_name'] + ' / ' + item['run_id'], i)
            if previous is not None:
                # Select by saved run identity, not transient list index.
                found = next((i for i, item in enumerate(runs)
                              if item['run_id'] == getattr(self, '_sf_selected_run_id', None)), 0)
                if runs:
                    self.sf_history.setCurrentIndex(found)
        finally:
            self.sf_history.blockSignals(False)
        self._sf_selected()

    def _sf_selected(self, _ignored=None):
        self.sf_table.setSortingEnabled(False)
        self.sf_table.clear()
        self.sf_details.clear()
        index = self.sf_history.currentData()
        if index is None or index < 0 or index >= len(self._sf_runs):
            self.sf_summary.setText('Ingen selvstendig Siegfried-kjøring lagret i valgt Work. '
                                    'Velg Siegfried i Enkel modus og kjør kontrollen.')
            self.sf_table.setSortingEnabled(True)
            return
        run = self._sf_runs[index]
        self._sf_selected_run_id = run['run_id']
        model = run['model']
        self.sf_summary.setText(
            f"Kilde: DWM / Siegfried | Filer: {model['files_total']} | "
            f"Identifisert: {model['identified']} | Ukjent: {model['unidentified']} | "
            f"Flertydig: {model['ambiguous']} | Grupper: {len(model['format_groups'])}. "
            'Arkade 5 telles ikke sammen med denne kjøringen.'
        )
        policy = getattr(self, '_a4_format_policy', None)
        for group in model['format_groups']:
            puid = str(group.get('puid') or '')
            decision = evaluate_puid(puid, policy)
            row = QTreeWidgetItem([
                puid or 'Ikke identifisert', str(group.get('format') or 'Ukjent'),
                str(group.get('version') or 'Ukjent'), str(group.get('count') or 0),
                decision.label,
            ])
            row.setToolTip(1, str(group.get('format') or ''))
            row.setToolTip(4, decision.explanation)
            row.setData(0, Qt.ItemDataRole.UserRole,
                        {'Valgt format': {'PUID': puid or 'Ikke identifisert',
                                          'Navn': group.get('format') or 'Ukjent',
                                          'Versjon': group.get('version') or '',
                                          'Antall': group.get('count')},
                         'Vurdering mot valgt regelprofil': {
                             'Status': decision.label,
                             'Begrunnelse': decision.explanation,
                         },
                         'Proveniens': {
                             'Kilde': 'Selvstendig DWM Siegfried (ikke Arkade 5)',
                             'Kjørings-ID': run['run_id'],
                             'Siegfried': model.get('siegfried_version'),
                             'PRONOM-signatur': model.get('siegfried_signature'),
                             'Omfang': model.get('source_scope'),
                             'Manifest': str(run['folder'] / 'manifest.json'),
                             'Originale identifikasjoner': str(run['folder'] / 'siegfried_files.jsonl'),
                             'SHA-256 råevidens': run['manifest'].get('raw_sha256'),
                         }})
            self.sf_table.addTopLevelItem(row)
        self.sf_table.setSortingEnabled(True)
        if self.sf_table.topLevelItemCount():
            self.sf_table.setCurrentItem(self.sf_table.topLevelItem(0))

    def _sf_show_detail(self, item, previous=None):
        if item is None:
            self.sf_details.clear()
            return
        self.sf_details.setHtml(readable_html(item.data(0, Qt.ItemDataRole.UserRole)))
        self.sf_details.moveCursor(QTextCursor.MoveOperation.Start)
        QTimer.singleShot(0, self._sf_reset_scroll)

    def _sf_reset_scroll(self):
        try:
            self.sf_details.verticalScrollBar().setValue(0)
        except RuntimeError:
            # A pending Qt callback must not touch a deleted result window.
            pass
