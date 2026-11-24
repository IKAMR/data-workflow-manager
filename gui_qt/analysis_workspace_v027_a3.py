"""v0.2.7-a3: resizable, filterable Analyse with the existing YearBarChart.

Reuses the read-only a2 result projection and original report-backed annual
series. Classic result windows, processing, exports and assessments are intact.
"""
from __future__ import annotations

import json
from html import escape
from types import SimpleNamespace

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPushButton, QScrollArea, QSplitter, QTableWidget, QTextBrowser,
    QVBoxLayout, QWidget,
)

from app.analysis_workspace_v027_a2 import (
    METRICS, annual_rows, delivery_rules, format_rows,
    part_title, part_identity, selected_parts,
)
from app.analysis_workspace_v027_a3 import (
    ANNUAL_FAMILIES, FILTERS, annual_chart_data, favorite_key,
    matches_filter, period_review_rows, result_state,
)
from .analysis_workspace_v027_a2 import (
    AnalysisWorkspaceDialog as _A2Workspace, LABELS, _safe,
)
# Retain the established Qt chart and its five separately dated metrics.
from .result_center_v018_a13 import YearBarChart


class _StandaloneDetails(QDialog):
    """Independent window, but lifetime-bound to the owning Analyse window."""

    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle('Analyse – detaljer')
        self.setMinimumSize(450, 300)
        self.resize(860, 690)
        layout = QVBoxLayout(self)
        self.title = QLabel('Valgt delresultat')
        self.title.setStyleSheet('font-weight: 600; font-size: 15px')
        layout.addWidget(self.title)
        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(False)
        layout.addWidget(self.browser, 1)
        note = QLabel('Viser samme lagrede evidens som i Analyse. Ingen endringer i Work.')
        note.setWordWrap(True)
        layout.addWidget(note)


class AnalysisWorkspaceDialogV3(_A2Workspace):
    """New UI over the same A2 model and detail renderers.

    We initialize QDialog directly so the old static panel tree does not need
    reparenting (unsafe in Qt). A2's scope, row and evidence methods are reused.
    """

    _KEY = 'analysis/v027_a3/'

    def __init__(self, snapshot, parent=None):
        QDialog.__init__(self, parent, Qt.WindowType.Window)
        self.snapshot = snapshot
        self._table_payloads = []
        self._detail_popup = None
        self.settings = QSettings('IKAMR', 'DWM-Qt')
        stored = self.settings.value(self._KEY + 'favorites', '[]')
        try:
            favorites = json.loads(stored) if isinstance(stored, str) else []
            self._favorites = set(str(item) for item in favorites if isinstance(item, str))
        except (ValueError, TypeError):
            self._favorites = set()
        self.setWindowTitle('Analyse – ' + snapshot.job_id + ' – ' + snapshot.job_name)
        self.setObjectName('dwm_analysis_v027_a3')
        self.resize(1480, 920)
        self.setMinimumSize(950, 640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(6)

        head = QLabel('Analyse – ' + snapshot.job_id + ' – ' + snapshot.job_name)
        head.setStyleSheet('font-weight: 600; font-size: 17px')
        head.setWordWrap(True)
        layout.addWidget(head)
        self.heading = head

        scope = QHBoxLayout()
        scope.addWidget(QLabel('Omfang:'))
        self.archive = QComboBox(self)
        self.archive.addItem('Hele uttrekket', 'all')
        if snapshot.archive_count == 1:
            self.archive.addItem('Arkiv 1 (eneste arkiv)', 'archive')
        elif snapshot.archive_count and snapshot.archive_count > 1:
            self.archive.addItem(f'{snapshot.archive_count} arkiver samlet', 'all_archives')
        self.archive.setToolTip('Arkivnivå er kun separat når tilhørigheten er entydig.')
        scope.addWidget(self.archive, 2)
        self.part = QComboBox(self)
        self.part.addItem('Alle arkivdeler', None)
        for i, part in enumerate(snapshot.parts):
            self.part.addItem(f'{i+1}. {part_title(part, i)}', i)
        scope.addWidget(self.part, 4)
        self.year = QComboBox(self)
        self.year.addItem('Alle år', '')
        self.year.setToolTip('Gjelder bare daterte tidsserier og kildemerkede årsfunn.')
        scope.addWidget(self.year, 1)
        layout.addLayout(scope)

        self.headline = QLabel('')
        self.headline.setWordWrap(True)
        self.headline.setStyleSheet('font-weight: 600; padding: 4px;')
        layout.addWidget(self.headline)

        filters = QHBoxLayout()
        filters.addWidget(QLabel('Vis:'))
        self.status_filter = QComboBox(self)
        for text, key in FILTERS:
            self.status_filter.addItem(text, key)
        filters.addWidget(self.status_filter)
        filters.addWidget(QLabel('Søk:'))
        self.search = QLineEdit(self)
        self.search.setPlaceholderText('M053, journalstatus, 2024, PDF/A, arkivdel …')
        filters.addWidget(self.search, 1)
        self.top_favorite = QPushButton('☆ Ofte sjekket', self)
        self.top_favorite.setToolTip('Merk eller fjern merking for valgt delresultat')
        self.top_favorite.clicked.connect(self._toggle_favorite)
        filters.addWidget(self.top_favorite)
        filters.addWidget(QLabel('Detaljer:'))
        self.details_mode = QComboBox(self)
        self.details_mode.addItem('Høyre', 'right')
        self.details_mode.addItem('Nede', 'bottom')
        self.details_mode.addItem('Eget vindu', 'window')
        filters.addWidget(self.details_mode)
        layout.addLayout(filters)

        # Area navigation / result table / detail browser are all splitter panes.
        self.content_split = QSplitter(Qt.Orientation.Horizontal, self)
        self.content_split.setChildrenCollapsible(False)
        self.areas = QListWidget(self.content_split)
        self.areas.setMinimumWidth(165)
        self.areas.setMaximumWidth(300)
        self.areas.addItem('Alle delresultater')
        for name in LABELS:
            self.areas.addItem(name)

        self.workspace_split = QSplitter(Qt.Orientation.Horizontal, self.content_split)
        self.workspace_split.setChildrenCollapsible(False)
        self.result_panel = QWidget(self.workspace_split)
        result_layout = QVBoxLayout(self.result_panel)
        result_layout.setContentsMargins(4, 0, 2, 0)
        result_layout.setSpacing(5)
        self.section = QLabel('')
        self.section.setStyleSheet('font-weight: 600; font-size: 15px')
        result_layout.addWidget(self.section)
        self.info = QLabel('')
        self.info.setWordWrap(True)
        result_layout.addWidget(self.info)

        self.chart_controls = QWidget(self.result_panel)
        controls = QHBoxLayout(self.chart_controls)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(7)
        controls.addWidget(QLabel('Stolpediagram:'))
        self.family_checks = []
        for title, metrics in ANNUAL_FAMILIES:
            check = QCheckBox(title, self.chart_controls)
            check.setChecked(True)
            check.setToolTip('Vis separate årsserier: ' + ', '.join(metrics))
            check.toggled.connect(self._update_chart)
            controls.addWidget(check)
            self.family_checks.append((check, metrics))
        self.chart_mode = QComboBox(self.chart_controls)
        self.chart_mode.addItem('Diagram + tall', 'both')
        self.chart_mode.addItem('Bare diagram', 'chart')
        self.chart_mode.addItem('Bare tall', 'table')
        self.chart_mode.currentIndexChanged.connect(self._chart_mode_changed)
        controls.addWidget(self.chart_mode)
        self.chart_controls.setVisible(False)
        result_layout.addWidget(self.chart_controls)

        self.data_split = QSplitter(Qt.Orientation.Vertical, self.result_panel)
        self.data_split.setChildrenCollapsible(False)
        self.chart_scroll = QScrollArea(self.data_split)
        self.chart_scroll.setWidgetResizable(False)
        self.chart_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chart_scroll.setMinimumHeight(155)
        self.chart = YearBarChart()
        self.chart_scroll.setWidget(self.chart)
        self.chart_scroll.hide()
        self.table = QTableWidget(self.data_split)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        result_layout.addWidget(self.data_split, 1)

        self.detail_panel = QWidget(self.workspace_split)
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(5, 0, 0, 0)
        detail_layout.setSpacing(5)
        detail_header = QHBoxLayout()
        detail_header.addWidget(QLabel('Delresultat og evidens'), 1)
        self.favorite = QPushButton('☆ Ofte sjekket', self.detail_panel)
        self.favorite.setToolTip('Merk dette kontrollpunktet som favoritt i Analyse')
        self.favorite.clicked.connect(self._toggle_favorite)
        detail_header.addWidget(self.favorite)
        detach = QPushButton('Eget vindu…', self.detail_panel)
        detach.clicked.connect(self._detach_details)
        detail_header.addWidget(detach)
        detail_layout.addLayout(detail_header)
        self.detail = QTextBrowser(self.detail_panel)
        self.detail.setOpenExternalLinks(False)
        detail_layout.addWidget(self.detail, 1)

        self.workspace_split.setStretchFactor(0, 3)
        self.workspace_split.setStretchFactor(1, 2)
        self.content_split.setStretchFactor(0, 1)
        self.content_split.setStretchFactor(1, 6)
        layout.addWidget(self.content_split, 1)

        footer = QHBoxLayout()
        self.footer = QLabel('Resultater fra Work · originaldata og faglige vedtak endres ikke')
        self.footer.setWordWrap(True)
        footer.addWidget(self.footer, 1)
        reload_button = QPushButton('Oppdater fra Work', self)
        reload_button.clicked.connect(self._reload)
        footer.addWidget(reload_button)
        close = QPushButton('Lukk', self)
        close.clicked.connect(self.close)
        footer.addWidget(close)
        layout.addLayout(footer)

        # Do not connect refresh signals until all controls exist.
        self.archive.currentIndexChanged.connect(self._refresh)
        self.part.currentIndexChanged.connect(self._part_changed)
        self.year.currentIndexChanged.connect(self._refresh)
        self.areas.currentRowChanged.connect(self._refresh)
        self.table.itemSelectionChanged.connect(self._detail_changed)
        self.table.cellDoubleClicked.connect(self._double_clicked)
        self.status_filter.currentIndexChanged.connect(self._refresh)
        self.search.textChanged.connect(self._refresh)
        self.details_mode.currentIndexChanged.connect(self._switch_details_mode)
        self.content_split.splitterMoved.connect(self._remember_content_size)
        self.workspace_split.splitterMoved.connect(self._remember_detail_size)
        self.data_split.splitterMoved.connect(self._remember_chart_size)

        saved = str(self.settings.value(self._KEY + 'detail_mode', 'right') or 'right')
        self.details_mode.setCurrentIndex(max(0, self.details_mode.findData(saved)))
        self.areas.setCurrentRow(0)
        self._part_changed()
        QTimer.singleShot(0, self._restore_sizes)

    def _area_index(self):
        return self.areas.currentRow() - 1

    @staticmethod
    def _known(value):
        return str(value) if value is not None else '–'

    def _global_rows(self):
        """One cross-area entry point, grounded in the selected scope.

        Imported format data remains clearly whole-extract-only even if a
        part or year is selected. Undated metadata findings never inherit year.
        """
        idx, year = self._part_index(), self._year()
        data, payloads = [], []

        def add(kind, payload, area, name, scope, value, deviations=None):
            data.append((area, name, scope, value, deviations))
            payloads.append((kind, payload))

        for i, part in enumerate(self.snapshot.parts):
            if idx is not None and i != idx:
                continue
            add('part', i, 'Struktur', part_title(part, i),
                'Arkivdel ' + str(i + 1),
                self._known(part.get('folder_count')) + ' mapper · ' +
                self._known(part.get('registration_count')) + ' registreringer')
        for y, values in annual_rows(self.snapshot, idx, year):
            add('year', y, 'Perioder og år', 'År ' + y,
                'Arkivdel ' + str(idx + 1) if idx is not None else 'Hele uttrekket',
                (str(values[0]) if values[0] is not None else '–') + ' mapper / ' +
                (str(values[1]) if values[1] is not None else '–') + ' registreringer')
        for item in period_review_rows(self.snapshot, idx, year):
            ev = item.get('year_evidence') or {}
            add('period_finding', item, 'Perioder og år',
                (str(item.get('summary') or 'Periodevurdering')[:92] +
                 ('…' if len(str(item.get('summary') or '')) > 92 else '')),
                ('År ' + str(ev.get('year')) if ev.get('year') else 'Hele uttrekket'),
                'Faglig vurdering')
        for rule in delivery_rules(self.snapshot, idx):
            add('metadata', rule, 'Metadata og verdier',
                rule['metadata_id'] + ' · ' + rule['label'],
                'Arkivdel ' + str(idx + 1) if idx is not None else 'Hele uttrekket',
                rule['observed'], rule['deviations'])
        for item in format_rows(self.snapshot):
            add('format', item, 'Dokumenter og filformater',
                item['puid'] + ' · ' + item['name'],
                'Hele uttrekksmappen (ikke avgrenset)', item['count'])
        for i, part in enumerate(self.snapshot.parts):
            if idx is not None and i != idx:
                continue
            add('preservation', i, 'Bevaring og skjerming',
                part_title(part, i), 'Arkivdel ' + str(i + 1),
                self._known(part.get('screening_count')) + ' skjerminger')
        self._rows(('Område', 'Delresultat', 'Omfang', 'Resultat', 'Avvik'),
                   data, payloads)

    def _get_sizes(self, key, fallback):
        value = self.settings.value(self._KEY + key, fallback)
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return fallback
        try:
            sizes = [int(x) for x in value]
            return sizes if all(n >= 80 for n in sizes) else fallback
        except (ValueError, TypeError):
            return fallback

    def _restore_sizes(self):
        self.content_split.setSizes(self._get_sizes('content_sizes', [220, 1140]))
        mode = str(self.details_mode.currentData())
        if mode in ('right', 'bottom'):
            key = 'right_sizes' if mode == 'right' else 'bottom_sizes'
            self.workspace_split.setSizes(self._get_sizes(key, [830, 520] if mode == 'right' else [520, 280]))
        self.data_split.setSizes(self._get_sizes('annual_sizes', [310, 440]))

    def _remember_content_size(self, *_):
        sizes = self.content_split.sizes()
        if len(sizes) == 2 and all(n > 0 for n in sizes):
            self.settings.setValue(self._KEY + 'content_sizes', sizes)

    def _remember_detail_size(self, *_):
        mode = str(self.details_mode.currentData() or '')
        if mode not in ('right', 'bottom'):
            return
        sizes = self.workspace_split.sizes()
        if len(sizes) == 2 and all(n > 0 for n in sizes):
            self.settings.setValue(self._KEY + mode + '_sizes', sizes)

    def _remember_chart_size(self, *_):
        sizes = self.data_split.sizes()
        if len(sizes) == 2 and all(n > 0 for n in sizes):
            self.settings.setValue(self._KEY + 'annual_sizes', sizes)

    def _current_favorite(self):
        index = self.table.currentRow()
        if index < 0 or index >= len(self._table_payloads):
            return ''
        kind, payload = self._table_payloads[index]
        return favorite_key(self.snapshot, kind, payload)

    def _toggle_favorite(self):
        key = self._current_favorite()
        if not key:
            return
        if key in self._favorites:
            self._favorites.remove(key)
        else:
            self._favorites.add(key)
        self.settings.setValue(self._KEY + 'favorites',
                               json.dumps(sorted(self._favorites), ensure_ascii=False))
        self._refresh()

    def _update_favorite_button(self):
        key = self._current_favorite()
        self.favorite.setEnabled(bool(key))
        self.favorite.setText('★ Ofte sjekket' if key in self._favorites else '☆ Ofte sjekket')
        self.top_favorite.setEnabled(bool(key))
        self.top_favorite.setText('★ Ofte sjekket' if key in self._favorites else '☆ Ofte sjekket')

    def _rows(self, headers, data, payloads):
        """Filter every area by the same rules, without changing its sources."""
        # The period page also exposes actual report findings as delresultater.
        if self._area_index() == 1:
            additions = period_review_rows(self.snapshot, self._part_index(), self._year())
            if additions:
                headers = ('År / kontroll',) + tuple(headers[1:])
                data = list(data) + [
                    ((('År ' + str((item.get('year_evidence') or {}).get('year'))
                       + ' – dokumentaktivitet')
                      if (item.get('year_evidence') or {}).get('year')
                      else 'Ulike observerte periodegrenser'),)
                    + tuple(None for _ in METRICS) for item in additions]
                payloads = list(payloads) + [('period_finding', item) for item in additions]
        key = str(self.status_filter.currentData() or 'all')
        query = self.search.text().strip().casefold()
        selected_rows = []
        selected_payloads = []
        for row, (kind, payload) in zip(data, payloads):
            category, display_status = result_state(
                self.snapshot, kind, payload, self._part_index())
            favorite = favorite_key(self.snapshot, kind, payload) in self._favorites
            if not matches_filter(category, key, favorite):
                continue
            haystack = ' '.join(str(x) for x in row).casefold()
            if kind == 'metadata':
                haystack += ' ' + str(payload.get('metadata_id') or '').casefold()
            if kind == 'period_finding':
                haystack += ' ' + str(payload.get('category') or '').casefold()
            if query and query not in haystack:
                continue
            selected_rows.append(tuple(row) + (display_status,))
            selected_payloads.append((kind, payload))
        super()._rows(tuple(headers) + ('Kontrollstatus',), selected_rows,
                      selected_payloads)
        # Show an explicit empty state rather than an unexplained blank table.
        if not selected_rows:
            self.detail.setHtml('<p>Ingen delresultater i valgt område som samsvarer med filteret.</p>')
        self._update_favorite_button()

    def _refresh(self, *_args):
        if self._area_index() == -1:
            self._update_headline()
            self.section.setText('Alle delresultater')
            self.info.setText('Felles filtrering på tvers av hovedområdene. '
                              'Avvik krever faglig behandling; ingen automatisk godkjenning.')
            self._global_rows()
        else:
            super()._refresh(*_args)
        self._update_chart()

    def _update_chart(self, *_args):
        if self._area_index() != 1:
            self.chart_controls.hide()
            self.chart_scroll.hide()
            self.table.show()
            return
        self.chart_controls.show()
        chosen = tuple(key for check, keys in self.family_checks if check.isChecked()
                       for key in keys)
        rows = annual_chart_data(self.snapshot, self._part_index(), self._year())
        self.chart.set_data(SimpleNamespace(rows=rows), chosen)
        self.chart.adjustSize()
        self._chart_mode_changed()

    def _chart_mode_changed(self, *_args):
        if self._area_index() != 1:
            return
        mode = str(self.chart_mode.currentData() or 'both')
        self.chart_scroll.setVisible(mode != 'table')
        self.table.setVisible(mode != 'chart')

    def _double_clicked(self, row, column):
        if (self._area_index() == -1 and 0 <= row < len(self._table_payloads)
                and self._table_payloads[row][0] == 'year'):
            year = str(self._table_payloads[row][1])
            self.areas.setCurrentRow(2)  # Perioder og år, after Alle delresultater
            position = self.year.findData(year)
            if position >= 0:
                self.year.setCurrentIndex(position)
            return
        super()._double_clicked(row, column)

    def _detail_changed(self):
        index = self.table.currentRow()
        if 0 <= index < len(self._table_payloads):
            kind, payload = self._table_payloads[index]
            if kind == 'period_finding':
                self.detail.setHtml('<h3>Periode – vurderingspunkt</h3><p>'
                                    + escape(str(payload.get('summary') or '')) + '</p>'
                                    + '<p>Kildeomfang: hele uttrekket. '
                                    'Vurderingen er ikke automatisk knyttet til en arkivdel.</p>')
            else:
                super()._detail_changed()
        else:
            super()._detail_changed()
        self._update_favorite_button()
        self._sync_popup()

    def _sync_popup(self):
        if self._detail_popup is None:
            return
        self._detail_popup.browser.setHtml(self.detail.toHtml())
        self._detail_popup.title.setText(self.section.text() + ' – valgt delresultat')

    def _detach_details(self):
        self.details_mode.setCurrentIndex(self.details_mode.findData('window'))
        if self._detail_popup is not None:
            self._detail_popup.show()
            self._detail_popup.raise_()

    def _popup_closed(self, *_args):
        if self.details_mode.currentData() == 'window':
            self.details_mode.setCurrentIndex(self.details_mode.findData('right'))

    def _switch_details_mode(self, *_args):
        mode = str(self.details_mode.currentData() or 'right')
        self.settings.setValue(self._KEY + 'detail_mode', mode)
        if mode == 'window':
            self.detail_panel.hide()
            if self._detail_popup is None:
                self._detail_popup = _StandaloneDetails(self)
                self._detail_popup.finished.connect(self._popup_closed)
            self._sync_popup()
            self._detail_popup.show()
            return
        if self._detail_popup is not None:
            self._detail_popup.hide()
        self.workspace_split.setOrientation(
            Qt.Orientation.Horizontal if mode == 'right' else Qt.Orientation.Vertical)
        self.detail_panel.show()
        key = 'right_sizes' if mode == 'right' else 'bottom_sizes'
        self.workspace_split.setSizes(self._get_sizes(
            key, [830, 520] if mode == 'right' else [520, 280]))


def install_analysis_workspace_v3(window) -> bool:
    """Update only the a2 Analyse dialog factory. Classic action is unchanged."""
    if not getattr(window, '_analysis_v027_a2_installed', False):
        return False
    window._analysis_dialog_class = AnalysisWorkspaceDialogV3
    window._analysis_v027_a3_installed = True
    return True
