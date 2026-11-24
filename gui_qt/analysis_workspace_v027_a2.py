"""v0.2.7-a2 Analyse: new read-only main result surface.

Existing result windows, menus, tools, calculations and review dialogs are
retained.  The classic result center stays on the Advanced Rapport menu.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView,
    QLabel, QListWidget, QMessageBox, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from app.analysis_workspace_v027_a2 import (
    AREAS, METRICS, AnalysisSnapshot, annual_rows, delivery_rules,
    format_rows, load_analysis, observed_span, part_identity, part_title,
    rule_findings, selected_parts, summary_counts,
)
from .appearance_v0110_a3 import stylesheet_for

# Keep the new navigation vocabulary independent of legacy KDRS job names.
LABELS = AREAS


def _value(v) -> str:
    return '\u2014' if v is None or v == '' else str(v)


def _safe(v) -> str:
    return escape(_value(v))


def _field(label: str, value) -> str:
    return '<p><b>' + escape(label) + ':</b> ' + _safe(value) + '</p>'


def _period(value) -> str:
    return str(value or '\u2014')[:10]


class AnalysisWorkspaceDialog(QDialog):
    """One navigable window. Selected year affects dated series only."""

    def __init__(self, snapshot: AnalysisSnapshot, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.snapshot = snapshot
        self._table_payloads = []
        self.setWindowTitle('Analyse \u2013 ' + snapshot.job_id + ' \u2013 ' + snapshot.job_name)
        self.setObjectName('dwm_analysis_v027_a2')
        self.resize(1360, 850)
        self.setMinimumSize(850, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(9)

        title = QLabel('Analyse \u2013 ' + snapshot.job_id + ' \u2013 ' + snapshot.job_name)
        title.setStyleSheet('font-size: 18px; font-weight: 600;')
        title.setWordWrap(True)
        layout.addWidget(title)
        self.heading = title
        subtitle = QLabel(
            'Kontrollomr\u00e5de \u2192 delresultat \u2192 observerte verdier og evidens. '
            'Kildeverkt\u00f8y er sekund\u00e6rt. Teknisk fullf\u00f8rt betyr ikke faglig godkjent.')
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        scope = QHBoxLayout()
        scope.addWidget(QLabel('Omfang:'))
        self.archive = QComboBox(self)
        self.archive.addItem('Hele uttrekket', 'all')
        if snapshot.archive_count == 1:
            self.archive.addItem('Arkiv 1 (eneste)', 'archive')
        elif snapshot.archive_count and snapshot.archive_count > 1:
            self.archive.addItem(f'{snapshot.archive_count} arkiver samlet', 'all_archives')
        self.archive.setToolTip('Arkivvisningen brukes bare separat n\u00e5r arkivtilh\u00f8righet er entydig.')
        scope.addWidget(self.archive, 2)
        self.part = QComboBox(self)
        self.part.addItem('Alle arkivdeler', None)
        for i, p in enumerate(snapshot.parts):
            self.part.addItem(f'{i+1}. {part_title(p, i)}', i)
        self.part.setMinimumWidth(260)
        scope.addWidget(self.part, 4)
        self.year = QComboBox(self)
        self.year.addItem('Alle \u00e5r', '')
        self.year.setToolTip('Filtrerer tidsserier etter egne datofelt. Endrer ikke udaterte funn.')
        scope.addWidget(self.year, 1)
        layout.addLayout(scope)
        self.archive.currentIndexChanged.connect(self._refresh)
        self.part.currentIndexChanged.connect(self._part_changed)
        self.year.currentIndexChanged.connect(self._refresh)

        self.headline = QLabel('')
        self.headline.setWordWrap(True)
        self.headline.setObjectName('analysisScopeSummary')
        self.headline.setStyleSheet('font-size: 13px; font-weight: 600; padding: 7px;')
        layout.addWidget(self.headline)

        content = QSplitter(Qt.Orientation.Horizontal, self)
        content.setChildrenCollapsible(False)
        self.areas = QListWidget(self)
        self.areas.setMinimumWidth(225)
        self.areas.setMaximumWidth(310)
        for label in LABELS:
            self.areas.addItem(label)
        self.areas.currentRowChanged.connect(self._refresh)
        content.addWidget(self.areas)

        main = QWidget(self)
        middle = QVBoxLayout(main)
        middle.setContentsMargins(8, 0, 0, 0)
        self.section = QLabel('')
        self.section.setStyleSheet('font-size: 16px; font-weight: 600;')
        middle.addWidget(self.section)
        self.info = QLabel('')
        self.info.setWordWrap(True)
        middle.addWidget(self.info)
        self.table = QTableWidget(self)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._detail_changed)
        self.table.cellDoubleClicked.connect(self._double_clicked)
        middle.addWidget(self.table, 3)
        self.detail = QTextBrowser(self)
        self.detail.setOpenExternalLinks(False)
        self.detail.setMinimumHeight(145)
        middle.addWidget(self.detail, 2)
        content.addWidget(main)
        content.setStretchFactor(0, 1)
        content.setStretchFactor(1, 5)
        layout.addWidget(content, 1)

        bottom = QHBoxLayout()
        self.footer = QLabel('Kun lesing av lagret Work. Originaldata, kj\u00f8ringer og vurderinger endres ikke.')
        self.footer.setWordWrap(True)
        bottom.addWidget(self.footer, 1)
        refresh = QPushButton('Oppdater fra Work')
        refresh.clicked.connect(self._reload)
        bottom.addWidget(refresh)
        close = QPushButton('Lukk')
        close.clicked.connect(self.close)
        bottom.addWidget(close)
        layout.addLayout(bottom)

        self.areas.setCurrentRow(0)
        self._part_changed()

    def _part_index(self):
        value = self.part.currentData()
        return value if isinstance(value, int) else None

    def _year(self) -> str:
        return str(self.year.currentData() or '')

    def _part_changed(self, *_args):
        old = self._year()
        with QSignalBlocker(self.year):
            self.year.clear()
            self.year.addItem('Alle \u00e5r', '')
            years = [yr for yr, _ in annual_rows(self.snapshot, self._part_index())]
            for yr in years:
                self.year.addItem(yr, yr)
            if old in years:
                self.year.setCurrentIndex(self.year.findData(old))
        self._refresh()

    def _reload(self):
        try:
            self.snapshot = load_analysis(self.snapshot.work, self.snapshot.job_id,
                                          self.snapshot.job_name,
                                          self.snapshot.job_uid)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Analyse', str(exc))
            return
        self._part_changed()

    def _update_headline(self):
        idx, year = self._part_index(), self._year()
        counts = summary_counts(self.snapshot, idx, year)
        years = observed_span(self.snapshot, idx)
        pieces = [f"{_value(counts['folders'])} mapper",
                  f"{_value(counts['registrations'])} registreringer",
                  f"{_value(counts['objects'])} dokumentobjekter"]
        scope = ('Arkivdel ' + str(idx + 1)) if idx is not None else 'Hele uttrekket'
        if self.archive.currentData() == 'archive' and idx is None:
            scope = 'Arkiv 1 (eneste arkiv)'
        if year:
            scope += ' / \u00e5r ' + year
        self.headline.setText(scope + '   \u2022   ' + '   \u2022   '.join(pieces)
                              + '   \u2022   observerte \u00e5r ' + years)

    def _rows(self, headers, data, payloads):
        self._table_payloads = list(payloads)
        self.table.blockSignals(True)
        try:
            self.table.clear()
            self.table.setRowCount(len(data))
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)
            for r, row in enumerate(data):
                for c, item in enumerate(row):
                    cell = QTableWidgetItem(_value(item))
                    self.table.setItem(r, c, cell)
            self.table.resizeColumnsToContents()
            self.table.horizontalHeader().setStretchLastSection(True)
            if data:
                self.table.selectRow(0)
        finally:
            self.table.blockSignals(False)
        self._detail_changed()

    def _refresh(self, *_args):
        if self.areas.currentRow() < 0:
            return
        self._update_headline()
        idx, year = self._part_index(), self._year()
        area = self.areas.currentRow()
        self.section.setText(LABELS[area])
        if area == 0:
            self.info.setText('Arkivdelene forblir synlige som eget niv\u00e5. Dobbeltklikk en arkivdel for \u00e5 avgrense analysen.')
            parts = [(i,p) for i,p in enumerate(self.snapshot.parts) if idx is None or idx == i]
            data = [(i+1, part_title(p, i), part_identity(p).get('status'),
                     p.get('folder_count'), p.get('registration_count'), p.get('document_object_count'))
                    for i,p in parts]
            self._rows(('Nr', 'Arkivdel', 'Arkivdelstatus', 'Mapper', 'Registreringer', 'Dok.obj.'),
                       data, [('part', i) for i,p in parts])
        elif area == 1:
            meta = self.snapshot.metadata.get('current') or {}
            period = (self.snapshot.report.get('period_reconciliation') or {}).get('declared_period') or {}
            hint = 'DIAS: ' + _period(meta.get('period_start')) + ' - ' + _period(meta.get('period_end'))
            hint += '   |   Uttrekksmetadata: ' + _period(period.get('start_date')) + ' - ' + _period(period.get('end_date'))
            self.info.setText(hint + '\n\u00c5rsseriene bruker ulike datofelt og m\u00e5 vurderes separat.')
            rows = annual_rows(self.snapshot, idx, year)
            self._rows(('\u00c5r',) + tuple(label for _,label in METRICS),
                       [(y,) + data for y,data in rows], [('year', y) for y,_ in rows])
        elif area == 2:
            status = 'Valgt \u00e5r avgrenser ikke metadata uten dokumentert datokobling. ' if year else ''
            if idx is not None:
                status += 'Antall observerte verdier finnes bare p\u00e5 uttrekksniv\u00e5; delavvik beregnes fra kildefunn.'
            else:
                status += 'Velg et M-felt for verdier i produksjon, avleveringsverdier og forekomster.'
            self.info.setText(status)
            rules = delivery_rules(self.snapshot, idx)
            self._rows(('M-felt', 'Delresultat', 'Observert', 'Avvik', 'Avleveringsverdier'),
                       [(r['metadata_id'], r['label'], r['observed'], r['deviations'],
                         ', '.join(r['delivery_values'])) for r in rules],
                       [('metadata', r) for r in rules])
        elif area == 3:
            self.info.setText('Filformatstatistikk gjelder hele uttrekksmappen, ikke et bestemt \u00e5r '
                              'eller en arkivdel. Identifikasjon er ikke formatvalidering eller godkjenning.')
            groups = format_rows(self.snapshot)
            self._rows(('PUID', 'Filformat', 'Versjon', 'Filer i inventar'),
                       [(g['puid'], g['name'], g['version'], g['count']) for g in groups],
                       [('format',g) for g in groups])
        else:
            self.info.setText('Telling per arkivdel. Ingen tidsfordeling er dokumentert for disse verdiene.')
            parts = [(i,p) for i,p in enumerate(self.snapshot.parts) if idx is None or idx == i]
            self._rows(('Arkivdel', 'Skjerming', 'Kassasjonsvedtak', 'Utf\u00f8rt kassasjon', 'Sletting'),
                       [(part_title(p,i), p.get('screening_count'),p.get('disposal_decision_count'),
                         p.get('performed_disposal_count'),p.get('deletion_count')) for i,p in parts],
                       [('preservation', i) for i,p in parts])

    def _detail_changed(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._table_payloads):
            self.detail.setHtml('<p>Ingen delresultater for valgt omfang.</p>')
            return
        kind, payload = self._table_payloads[row]
        body = ''
        if kind in ('part', 'preservation'):
            part = self.snapshot.parts[payload]
            identity = part_identity(part)
            body = '<h3>' + escape(part_title(part,payload)) + '</h3>'
            body += _field('System-ID', identity.get('system_id'))
            body += _field('Status', identity.get('status'))
            body += _field('Arkivperiode i XML', _period(identity.get('archive_period_start_date'))
                           + ' - ' + _period(identity.get('archive_period_end_date')))
            body += _field('Opprettet / avsluttet', _period(identity.get('created_date'))
                           + ' - ' + _period(identity.get('closed_date')))
            body += _field('Observert \u00e5rsspenn', observed_span(self.snapshot,payload))
        elif kind == 'year':
            body = '<h3>\u00c5r ' + escape(payload) + '</h3>'
            body += '<p>Tallene stammer fra forskjellige datoegenskaper; '
            body += 'det er ikke en felles hendelsesdato.</p>'
        elif kind == 'metadata':
            rule = payload
            mid = rule['metadata_id']
            body = '<h3>' + escape(mid) + ' - ' + escape(rule['label']) + '</h3>'
            body += _field('Noark-versjon', rule['version'])
            body += '<table cellspacing="0" cellpadding="5"><tr><th>Verdi</th><th>Observert</th>'
            body += '<th>Produksjon</th><th>Avlevering</th></tr>'
            values = tuple(dict.fromkeys((*rule['production_values'],
                                         *rule['production_distribution'],
                                         *rule['delivery_values'])))
            for value in values:
                count = (rule['production_distribution'].get(value)
                         if self._part_index() is None else None)
                production = ('Ja' if value in rule['production_values'] else
                              'Ikke dokumentert i registeret')
                delivered = 'Ja' if value in rule['delivery_values'] else 'Nei'
                body += ('<tr><td>' + _safe(value) + '</td><td>' + _safe(count)
                         + '</td><td>' + production + '</td><td>' + delivered + '</td></tr>')
            body += '</table>'
            if not rule['production_values']:
                body += '<p>Komplett produksjonsverdiliste er ikke registrert for denne versjonen.</p>'
            if self._part_index() is not None:
                body += '<p>Full verdifordeling for denne arkivdelen er ikke dokumentert i rapporten.</p>'
            body += _field('Kilde', rule['source_title'])
            body += _field('Kildeside', rule['source_page'])
            if rule['source_status'] and rule['source_status'] != 'verified':
                body += '<p>Kildemanifest: ' + _safe(rule['source_status'])
                body += '. Tolkningen er ikke endelig kildegodkjent.</p>'
            findings = rule_findings(self.snapshot, mid, self._part_index())
            if self.snapshot.findings_complete:
                body += '<b>Konkrete avvik (' + str(len(findings)) + ')</b><ol>'
                for f in findings[:40]:
                    body += '<li>' + _safe(f.get('value')) + ' | Objekt: ' + _safe(f.get('object_id'))
                    body += ' | XML: ' + _safe(f.get('file')) + ' | XPath: ' + _safe(f.get('xpath')) + '</li>'
                body += '</ol>'
                if len(findings)>40:
                    body += '<p>Flere funn finnes i original JSONL/CSV i Work.</p>'
            else:
                body += '<p>Fullstendig forekomstfil er ikke tilgjengelig. '
                body += 'Avvik kan derfor ikke avgrenses p\u00e5litelig.</p>'
            if self._year():
                body += '<p>Valgt \u00e5r brukes ikke p\u00e5 disse funnene uten eksplisitt dato.</p>'
        elif kind == 'format':
            body = '<h3>' + _safe(payload['puid']) + ' - ' + _safe(payload['name']) + '</h3>'
            body += _field('Identifiserte filer', payload['count'])
            body += _field('Versjon', payload['version'])
            body += '<p>Filformatregler og per-arkivdel-filtilordning er ikke vurdert p\u00e5 dette steget.</p>'
        self.detail.setHtml(body)

    def _double_clicked(self, row: int, _column: int):
        if row < len(self._table_payloads) and self._table_payloads[row][0] == 'part':
            i = self._table_payloads[row][1]
            self.part.setCurrentIndex(self.part.findData(i))


def install_analysis_workspace(window) -> bool:
    """Route primary result opening to Analyse without replacing the old GUI.

    The Rapport menu QAction already holds its original bound Qt callback,
    and remains the classic result center. Depot review also stays classic.
    """
    if not hasattr(window, 'api') or not callable(getattr(window,'_a12_open_result_center',None)):
        return False
    if getattr(window, '_analysis_v027_a2_installed', False):
        return True
    legacy = window._a12_open_result_center
    window._analysis_classic_result_center = legacy
    window._analysis_windows_v027_a2 = []

    def open_analysis(_checked=False):
        active = str(getattr(window, '_basic_job_id', None) or ''
                     if getattr(window, '_basic_active', False)
                     else getattr(window, '_active_id', None) or '')
        if not active:
            QMessageBox.information(window, 'Analyse', 'Velg en jobb f\u00f8rst.')
            return
        try:
            job = window.api.job_details(active).job
            work = getattr(job,'effective_work_operations',None)
            if not work:
                raise FileNotFoundError('Valgt jobb har ingen Work-mappe.')
            snapshot = load_analysis(Path(work), str(getattr(job,'job_id',active)),
                                     str(getattr(job,'name','')),
                                     str(getattr(job,'job_uid','') or ''))
        except (OSError, ValueError, AttributeError) as exc:
            QMessageBox.warning(window, 'Analyse', str(exc))
            return
        dialog = AnalysisWorkspaceDialog(snapshot, window)
        dialog.setStyleSheet(stylesheet_for(window.api.settings))
        dialog.setFont(window.font())
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window._analysis_windows_v027_a2.append(dialog)
        dialog.destroyed.connect(lambda _obj=None, d=dialog: (
            window._analysis_windows_v027_a2.remove(d)
            if d in window._analysis_windows_v027_a2 else None))
        dialog.show()
        if callable(getattr(window, '_a3_place_dialog', None)):
            window._a3_place_dialog(dialog, 'results')

    def route_main(_checked=False, *, depot=False):
        if depot:
            return legacy(_checked, depot=True)
        return open_analysis(_checked)

    # A Simple-mode button invokes _open_basic_results, which dynamically calls
    # _a12_open_result_center. The original advanced QAction callback stays bound
    # to the original method and therefore still opens the full classic window.
    window._a12_open_result_center = route_main
    if hasattr(window, 'basic_results_button'):
        window.basic_results_button.setText('Analyse\u2026')
    if hasattr(window, '_a3_auto_results'):
        window._a3_auto_results.setText('\u00c5pne Analyse etter kj\u00f8ring')
    for action in (getattr(window, 'result_center_action', None),):
        if action is not None:
            action.setText('Resultatvisninger (klassisk)\u2026')
    menu = next((action.menu() for action in window.menuBar().actions()
                 if action.menu() and action.menu().title().replace('&','') == 'Rapport'), None)
    if menu is not None:
        new_action = QAction('Analyse\u2026', window)
        new_action.triggered.connect(open_analysis)
        menu.insertAction(window.result_center_action, new_action)
        window._analysis_action_v027_a2 = new_action
    window._analysis_v027_a2_installed = True
    return True
