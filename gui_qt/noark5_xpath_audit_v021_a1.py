"""Read-only XPath source and stored-result explorer for the Qt result centre.

Same established Work snapshots and saved lxml results as the existing viewer.
No new XPath execution, document scanning or unverified normative claims.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QTabWidget,
)

from app.noark5_xpath_regression_v021_a2 import source_crosswalk
from app.noark5_xpath_metadata_qa_v021_a4 import build_metadata_qa, filter_metadata_rows
from app.noark_semantic_values_v021_a6 import load_registry
from app.noark5_requirement_matrix_v021_a7 import (
    REPORT_TYPE as A7_MATRIX_REPORT_TYPE, filter_matrix_rows,
)
from app.noark5_requirement_review_v021_a8 import (
    REPORT_TYPE as A8_REVIEW_REPORT_TYPE, filter_review_rows,
)
from app.noark5_xpath_version_qa_v021_a3 import build_version_audit, filter_version_rows

from app.noark5_xpath_audit_v021_a1 import (
    STATUS_ORDER, VERSIONS, candidate_schema_root, catalogue_summary, classify_execution,
    filter_work_rows, legacy_job_audit, legacy_source_expression, load_rows, project_work_rows,
    repo_root, schema_inventory, schema_lexical_coverage, _read_json,
)


_VERSION_LABELS = {
    'needs_version_qa': 'Krever kilde-QA',
    'source_verified_version_link': 'Kildehenvisning verifisert',
    'registry_unavailable': 'Kilderegister mangler',
    'reference_conflict': 'Referansekonflikt',
    'not_declared': 'Ikke deklarert',
}

_LABELS = {
    'FEIL': 'FEIL', 'WARNING': 'WARNING / Vurder', 'NOTE': 'NOTE / Merknad',
    'MANGLER': 'Mangler kilde', 'UKJENT': 'Ukjent', 'UTFORT': 'Utf\u00f8rt teknisk',
    'IKKE_KJORT': 'Ikke kj\u00f8rt', 'REGRESJON': 'U1/U2 regresjon',
}


def _preview_json(value, *, limit=75_000):
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except (ValueError, TypeError):
        text = str(value)
    return text if len(text) <= limit else text[:limit] + '\n[Visningen er forkortet. Se lagret JSON-fil.]'


class XPathCoverageDialog(QDialog):
    """Browse all defined jobs and the selected Work run; no implicit approvals."""

    def __init__(self, viewer):
        super().__init__(viewer, Qt.WindowType.Window)
        self.setWindowTitle('Noark 5 - XPath, KDRS Standard / U1 / U2')
        self.setMinimumSize(820, 550)
        self.resize(1280, 840)
        self._rows = load_rows()
        self._work = tuple(getattr(viewer, '_snapshots', ()) or ())
        self._projected = ()
        self._base_projected = ()
        self._visible_rows = ()
        self._schema = None
        self._schema_root = candidate_schema_root()
        self._legacy = legacy_job_audit()
        self._source_audit = source_crosswalk(self._rows)["tests"]
        self._version_audit = build_version_audit(rows=self._rows, schema_root=self._schema_root)
        self._metadata_audit = build_metadata_qa(rows=self._rows)
        self._semantic_registry = load_registry()
        self._semantic_entries = []
        self._coverage_report = None
        self._coverage_entries = []
        self._a8_report = None
        self._a8_entries = []
        self._a8_kdrs_entries = []

        outer = QVBoxLayout(self)
        intro = QLabel(
            'Alle deklarerte DWM XPath-kontroller, med kildekobling til KDRS Query Standard, '
            'U1 og U2. Lagret kjørestatus er ikke Noark-godkjenning. '
            'En WARNING er et vurderingspunkt, ikke automatisk brudd på standarden.', self)
        intro.setWordWrap(True)
        outer.addWidget(intro)

        top = QHBoxLayout()
        top.addWidget(QLabel('Jobb:', self))
        self.job = QComboBox(self)
        self.job.addItem('Bare katalog / ingen jobb', -1)
        for i, shot in enumerate(self._work):
            self.job.addItem(shot.job.job_id + ' - ' + shot.job.name, i)
        if self._work:
            self.job.setCurrentIndex(1)
        top.addWidget(self.job, 2)
        top.addWidget(QLabel('Noark-versjon:', self))
        self.version = QComboBox(self)
        self.version.addItem('Alle - ingen normtolkning', '')
        for v in VERSIONS:
            self.version.addItem('Noark 5 v' + v, v)
        top.addWidget(self.version, 1)
        outer.addLayout(top)

        controls = QHBoxLayout()
        controls.addWidget(QLabel('Vis:', self))
        self.severity = QComboBox(self)
        self.severity.addItem('Alle statuskategorier', '')
        for s in STATUS_ORDER:
            self.severity.addItem(_LABELS.get(s, s), s)
        controls.addWidget(self.severity)
        self.source = QComboBox(self)
        for label, key in (('Alle KDRS / DWM', ''), ('Standard', 'Standard'),
                           ('U1 / U2', 'U1/U2'), ('DWM-egne', 'DWM')):
            self.source.addItem(label, key)
        controls.addWidget(self.source)
        self.mapping = QComboBox(self)
        for title, key in (
            ('Alle KDRS-formelkoblinger', ''),
            ('Alle deklarerte fragmenter funnet', 'all_literal_fragments_found'),
            ('Delvis fragmenttreff', 'partial_fragments_found'),
            ('Krever semantisk gjennomgang', 'manual_semantics_review'),
            ('Særskilt Python / sammensatt', 'special_or_composite_review'),
            ('Ukjent original / kildekonflikt', 'source_problem'),
            ('Egne DWM-tester', 'dwm_extension'),
        ):
            self.mapping.addItem(title, key)
        self.mapping.setToolTip('Kildekobling er ikke bevist lik KDRS/Saxon-semantikk.')
        self.search = QLineEdit(self)
        self.search.setPlaceholderText('Søk: XPath, C15, U01, M300, testnavn, kildefil...')
        controls.addWidget(self.search, 1)
        outer.addLayout(controls)
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel('KDRS-formelkobling:', self))
        source_row.addWidget(self.mapping, 1)
        source_row.addWidget(QLabel('Versjons-QA:', self))
        self.version_qa_filter = QComboBox(self)
        for title, key in (
            ('Alle versjonstilstander', ''),
            ('Krever kildekontroll', 'needs_version_qa'),
            ('Verifisert kildehenvisning', 'source_verified_version_link'),
            ('Kilderegister utilgjengelig', 'registry_unavailable'),
            ('Referansekonflikt', 'reference_conflict'),
            ('Ikke deklarert for versjonen', 'not_declared'),
            ('Registrert verdi-sett', 'has_value_set_link'),
            ('Registrert normativ kravreferanse', 'has_requirement_reference'),
        ):
            self.version_qa_filter.addItem(title, key)
        self.version_qa_filter.setToolTip(
            'Gjelder versjons- og kildedekning, IKKE om Noark-kontrollen er bestått.')
        source_row.addWidget(self.version_qa_filter, 1)
        outer.addLayout(source_row)
        meta_row = QHBoxLayout()
        meta_row.addWidget(QLabel('Metadata / krav:', self))
        self.metadata_filter = QComboBox(self)
        for title, key in (
            ('Alle koblinger', ''),
            ('XPath omtaler metadatafelt', 'xpath_candidate'),
            ('Eksplisitt verdi-settreferanse', 'explicit_value_set_reference'),
            ('Ingen metadata-kandidat', 'no_metadata_candidate'),
            ('XPath kan omtale registrert krav', 'requirement_candidate'),
            ('Eksplisitt kravreferanse', 'explicit_requirement_reference'),
        ):
            self.metadata_filter.addItem(title, key)
        self.metadata_filter.setToolTip(
            'Kobling er ikke bevis for at M-feltet eller kravet er validert.')
        meta_row.addWidget(self.metadata_filter, 1)
        meta_row.addWidget(QLabel('Alle registrerte metadata og krav finnes i egen fane.', self), 2)
        outer.addLayout(meta_row)

        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        outer.addWidget(self.summary)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        self.table = QTreeWidget(splitter)
        self.table.setHeaderLabels(('Niv\u00e5', 'KDRS-ID', 'DWM-test', 'Kontroll / analyse',
                                    'Kilde-XML', 'Omfang', 'Versjoner', 'Versjon QA'))
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setUniformRowHeights(True)
        header = self.table.header()
        header.setStretchLastSection(False)
        for col, width in ((0, 95), (1, 86), (2, 120), (3, 270),
                           (4, 138), (5, 120), (6, 96), (7, 150)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col, width)
        splitter.addWidget(self.table)
        details = QWidget(splitter)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(4, 0, 0, 0)
        details_layout.addWidget(QLabel('Testdefinisjon, XPath og lagret evidens', details))
        self.detail = QPlainTextEdit(details)
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        option = self.detail.document().defaultTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.detail.document().setDefaultTextOption(option)
        details_layout.addWidget(self.detail, 1)
        self.open_result = QPushButton('\u00c5pne lagret test-JSON', details)
        self.open_result.setEnabled(False)
        details_layout.addWidget(self.open_result)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes((740, 500))
        # A second work surface in the SAME dialog. No nested file picker or popup.
        self.results_tabs = QTabWidget(self)
        self.results_tabs.addTab(splitter, 'XPath-kontroller')
        metadata_page = QWidget(self.results_tabs)
        metadata_layout = QVBoxLayout(metadata_page)
        metadata_layout.setContentsMargins(5, 5, 5, 5)
        metadata_note = QLabel(
            'Kilderegistrerte M-felt og normative krav per valgt Noark-versjon. '
            'XPath-kandidater og verdi-settreferanser er IKKE bestått validering.',
            metadata_page)
        metadata_note.setWordWrap(True)
        metadata_layout.addWidget(metadata_note)
        self.metadata_summary = QLabel(metadata_page)
        self.metadata_summary.setWordWrap(True)
        metadata_layout.addWidget(self.metadata_summary)
        self.metadata_splitter = QSplitter(Qt.Orientation.Horizontal, metadata_page)
        self.metadata_splitter.setChildrenCollapsible(False)
        self.metadata_table = QTreeWidget(self.metadata_splitter)
        self.metadata_table.setRootIsDecorated(False)
        self.metadata_table.setUniformRowHeights(True)
        self.metadata_table.setHeaderLabels((
            'Type', 'ID', 'Felt / krav', 'Noark', 'XPath-kandidater', 'Kobling'))
        meta_header = self.metadata_table.header()
        meta_header.setStretchLastSection(False)
        for col, width in ((0, 85), (1, 120), (2, 260), (3, 68), (4, 122), (5, 190)):
            meta_header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.metadata_table.setColumnWidth(col, width)
        self.metadata_splitter.addWidget(self.metadata_table)
        self.metadata_detail = QPlainTextEdit(self.metadata_splitter)
        self.metadata_detail.setReadOnly(True)
        self.metadata_detail.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.metadata_splitter.addWidget(self.metadata_detail)
        self.metadata_splitter.setSizes((650, 520))
        metadata_layout.addWidget(self.metadata_splitter, 1)
        self.results_tabs.addTab(metadata_page, 'Metadata og krav')

        # a6: one stable meaning-ID for multiple raw text variants. This tab
        # shows the versioned *registry*, never pretends that a semantic alias
        # makes the observed raw value pass the original XSD.
        semantic_page = QWidget(self.results_tabs)
        semantic_layout = QVBoxLayout(semantic_page)
        semantic_layout.setContentsMargins(5, 5, 5, 5)
        meaning_note = QLabel(
            'Menings-ID-er og kildeliteraler fra våre Noark 5-XSD-er. '
            'Varianter/QA-kandidater vises uten å endre råverdier. '
            'Dette er ikke XSD-validering eller normativ godkjenning.', semantic_page)
        meaning_note.setWordWrap(True)
        semantic_layout.addWidget(meaning_note)
        self.semantic_summary = QLabel(semantic_page)
        self.semantic_summary.setWordWrap(True)
        semantic_layout.addWidget(self.semantic_summary)
        semantic_splitter = QSplitter(Qt.Orientation.Horizontal, semantic_page)
        semantic_splitter.setChildrenCollapsible(False)
        self.semantic_table = QTreeWidget(semantic_splitter)
        self.semantic_table.setRootIsDecorated(False)
        self.semantic_table.setUniformRowHeights(True)
        self.semantic_table.setHeaderLabels((
            'Metadata', 'Menings-ID', 'Referanseverdi', 'XSD for valgt versjon', 'Varianter'))
        semantic_header = self.semantic_table.header()
        semantic_header.setStretchLastSection(False)
        for col, width in ((0, 90), (1, 145), (2, 310), (3, 200), (4, 90)):
            semantic_header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.semantic_table.setColumnWidth(col, width)
        semantic_splitter.addWidget(self.semantic_table)
        self.semantic_detail = QPlainTextEdit(semantic_splitter)
        self.semantic_detail.setReadOnly(True)
        self.semantic_detail.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        semantic_splitter.addWidget(self.semantic_detail)
        semantic_splitter.setSizes((720, 430))
        semantic_layout.addWidget(semantic_splitter, 1)
        self.results_tabs.addTab(semantic_page, 'Verdier og menings-ID')

        # a7: inspect a read-only, locally generated matrix from our original
        # Noark source checkout. No automatic normalization or normative pass.
        coverage_page = QWidget(self.results_tabs)
        coverage_layout = QVBoxLayout(coverage_page)
        coverage_layout.setContentsMargins(5, 5, 5, 5)
        coverage_note = QLabel(
            'Teknisk kilde-/kravmatrise fra originalspesifikasjoner og 15 XSD-er. '
            'FEIL/WARNING/NOTE gjelder kontroll av kilde- og testdekning, '
            'ikke feil i et bestemt arkivuttrekk. Kildetreff er ikke bestått Noark-krav.',
            coverage_page)
        coverage_note.setWordWrap(True)
        coverage_layout.addWidget(coverage_note)
        coverage_controls = QHBoxLayout()
        self.coverage_load = QPushButton('Åpne generert a7 QA-matrise (.json)...', coverage_page)
        coverage_controls.addWidget(self.coverage_load)
        coverage_controls.addWidget(QLabel('QA-status:', coverage_page))
        self.coverage_status = QComboBox(coverage_page)
        for label, state in (('Alle', ''), ('FEIL - kildekonflikt', 'FEIL'),
                             ('WARNING - QA / manglende dekning', 'WARNING'),
                             ('NOTE - kandidat / informasjon', 'NOTE')):
            self.coverage_status.addItem(label, state)
        coverage_controls.addWidget(self.coverage_status)
        coverage_controls.addStretch(1)
        coverage_layout.addLayout(coverage_controls)
        self.coverage_summary = QLabel(coverage_page)
        self.coverage_summary.setWordWrap(True)
        coverage_layout.addWidget(self.coverage_summary)
        coverage_splitter = QSplitter(Qt.Orientation.Horizontal, coverage_page)
        coverage_splitter.setChildrenCollapsible(False)
        self.coverage_table = QTreeWidget(coverage_splitter)
        self.coverage_table.setRootIsDecorated(False)
        self.coverage_table.setUniformRowHeights(True)
        self.coverage_table.setHeaderLabels((
            'QA', 'Noark', 'Type', 'ID / kilde', 'Felt / beskrivelse', 'XPath-kandidater'))
        c_header = self.coverage_table.header()
        c_header.setStretchLastSection(False)
        for col, width in ((0, 85), (1, 65), (2, 95), (3, 205), (4, 255), (5, 120)):
            c_header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.coverage_table.setColumnWidth(col, width)
        coverage_splitter.addWidget(self.coverage_table)
        self.coverage_detail = QPlainTextEdit(coverage_splitter)
        self.coverage_detail.setReadOnly(True)
        self.coverage_detail.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        coverage_splitter.addWidget(self.coverage_detail)
        coverage_splitter.setSizes((790, 400))
        coverage_layout.addWidget(coverage_splitter, 1)
        self.results_tabs.addTab(coverage_page, 'Kravmatrise og XSD')

        # a8: separate, explicit review file; no automatic scan of arbitrary
        # local directories and no mutation of the normative requirements JSON.
        a8_page = QWidget(self.results_tabs)
        a8_layout = QVBoxLayout(a8_page)
        a8_layout.setContentsMargins(5, 5, 5, 5)
        a8_note = QLabel(
            'Krav- og KDRS-review fra lokal originalkilde: XLSX-rader, PDF-linjekandidater, '
            'leksikale referanser og eksplisitte DWM-krav holdes atskilt. '
            'FEIL/WARNING/NOTE er kilde-QA, aldri automatisk Noark-samsvar.',a8_page)
        a8_note.setWordWrap(True)
        a8_layout.addWidget(a8_note)
        a8_controls = QHBoxLayout()
        self.a8_load = QPushButton('Åpne a8 kravreview (.json)...',a8_page)
        a8_controls.addWidget(self.a8_load)
        a8_controls.addWidget(QLabel('QA:',a8_page))
        self.a8_status = QComboBox(a8_page)
        for label,status in (('Alle',''),('FEIL','FEIL'),('WARNING','WARNING'),('NOTE','NOTE')):
            self.a8_status.addItem(label,status)
        a8_controls.addWidget(self.a8_status)
        a8_controls.addWidget(QLabel('Kilde:',a8_page))
        self.a8_origin = QComboBox(a8_page)
        for label,key in (
            ('Alle kilder',''),('Kravrad XLSX','xlsx_numbered_row'),
            ('PDF-kandidat','pdf_numbered_line_candidate'),
            ('Ubekreftet talltreff','a7_lexical_number_only'),
            ('Registrert DWM-krav','existing_dwm_partial_requirements_registry')):
            self.a8_origin.addItem(label,key)
        a8_controls.addWidget(self.a8_origin)
        a8_controls.addStretch(1)
        a8_layout.addLayout(a8_controls)
        self.a8_summary = QLabel(a8_page)
        self.a8_summary.setWordWrap(True)
        a8_layout.addWidget(self.a8_summary)
        self.a8_subtabs = QTabWidget(a8_page)
        a8_requirements = QWidget(self.a8_subtabs)
        ar_layout = QVBoxLayout(a8_requirements)
        ar_split = QSplitter(Qt.Orientation.Horizontal,a8_requirements)
        self.a8_table = QTreeWidget(ar_split)
        self.a8_table.setRootIsDecorated(False)
        self.a8_table.setUniformRowHeights(True)
        self.a8_table.setHeaderLabels(('QA','Noark','ID','Kildekategori','Kravtekst','XPaths'))
        self.a8_table.setColumnWidth(0,90)
        self.a8_table.setColumnWidth(1,66)
        self.a8_table.setColumnWidth(2,150)
        self.a8_table.setColumnWidth(3,220)
        self.a8_table.setColumnWidth(4,320)
        self.a8_detail = QPlainTextEdit(ar_split)
        self.a8_detail.setReadOnly(True)
        ar_split.setSizes((800,400))
        ar_layout.addWidget(ar_split)
        self.a8_subtabs.addTab(a8_requirements,'Krav og kildekandidater')
        a8_kdrs = QWidget(self.a8_subtabs)
        ak_layout = QVBoxLayout(a8_kdrs)
        ak_note = QLabel('Teknisk sjekk av 60 KDRS/DWM-jobber og spesialbehandlernes dispatch. '
                         'Saxon/lxml-resultatlikhet er ikke attestert.',a8_kdrs)
        ak_note.setWordWrap(True)
        ak_layout.addWidget(ak_note)
        ak_split = QSplitter(Qt.Orientation.Horizontal,a8_kdrs)
        self.a8_kdrs_table = QTreeWidget(ak_split)
        self.a8_kdrs_table.setRootIsDecorated(False)
        self.a8_kdrs_table.setUniformRowHeights(True)
        self.a8_kdrs_table.setHeaderLabels(('QA','KDRS-ID','DWM-test','Kjøringsart','Teknisk dispatch'))
        self.a8_kdrs_table.setColumnWidth(0,90)
        self.a8_kdrs_table.setColumnWidth(1,100)
        self.a8_kdrs_table.setColumnWidth(2,180)
        self.a8_kdrs_table.setColumnWidth(3,220)
        self.a8_kdrs_detail = QPlainTextEdit(ak_split)
        self.a8_kdrs_detail.setReadOnly(True)
        ak_split.setSizes((700,480))
        ak_layout.addWidget(ak_split)
        self.a8_subtabs.addTab(a8_kdrs,'KDRS Standard/U1/U2 - teknisk QA')
        a8_layout.addWidget(self.a8_subtabs,1)
        self.results_tabs.addTab(a8_page,'Krav- og KDRS-review a8')
        outer.addWidget(self.results_tabs, 1)

        bottom = QHBoxLayout()
        self.schema_info = QLabel(self)
        self.schema_info.setWordWrap(True)
        bottom.addWidget(self.schema_info, 1)
        choose_schema = QPushButton('Velg lokalt XSD-bibliotek...', self)
        choose_schema.clicked.connect(self._choose_schema)
        bottom.addWidget(choose_schema)
        view_schema = QPushButton('Vis XSD-kartlegging...', self)
        view_schema.clicked.connect(self._view_schema)
        bottom.addWidget(view_schema)
        refresh = QPushButton('Oppdater fra Work', self)
        refresh.clicked.connect(self._refresh_source)
        bottom.addWidget(refresh)
        close = QPushButton('Lukk', self)
        close.clicked.connect(self.close)
        bottom.addWidget(close)
        outer.addLayout(bottom)

        self.job.currentIndexChanged.connect(self._refresh_source)
        self.version.currentIndexChanged.connect(self._apply_version)
        self.source.currentIndexChanged.connect(self._filter)
        self.mapping.currentIndexChanged.connect(self._filter)
        self.version_qa_filter.currentIndexChanged.connect(self._filter)
        self.metadata_filter.currentIndexChanged.connect(self._filter)
        self.severity.currentIndexChanged.connect(self._filter)
        self.search.textChanged.connect(self._filter)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.metadata_table.itemSelectionChanged.connect(self._metadata_selection_changed)
        self.semantic_table.itemSelectionChanged.connect(self._semantic_selection_changed)
        self.coverage_load.clicked.connect(self._choose_coverage_report)
        self.a8_load.clicked.connect(self._choose_a8_report)
        self.a8_status.currentIndexChanged.connect(self._render_a8)
        self.a8_origin.currentIndexChanged.connect(self._render_a8)
        self.a8_table.itemSelectionChanged.connect(self._a8_selection_changed)
        self.a8_kdrs_table.itemSelectionChanged.connect(self._a8_kdrs_selection_changed)
        self.coverage_status.currentIndexChanged.connect(self._render_coverage)
        self.coverage_table.itemSelectionChanged.connect(self._coverage_selection_changed)
        self.open_result.clicked.connect(self._open_result)
        self._refresh_schema_summary()
        self._refresh_source()

    def _current_shot(self):
        index = self.job.currentData()
        return self._work[index] if isinstance(index, int) and 0 <= index < len(self._work) else None

    def _refresh_source(self, *_unused):
        # Work files are read only on explicit refresh or job switch, not every
        # time the user changes a Noark-version or severity filter on a network drive.
        self._base_projected = project_work_rows(self._rows, self._current_shot())
        self._apply_version()

    def _apply_version(self, *_unused):
        version = str(self.version.currentData() or '')
        projected = []
        for item in self._base_projected:
            severity, reasons = classify_execution(item['row'], item['index_entry'],
                                                   item['result'], version=version)
            projected.append({**item, 'severity': severity, 'reasons': reasons})
        self._projected = tuple(projected)
        self._filter()

    def _filter(self, *_unused):
        previous = self._current_record()
        previous_id = previous['row'].test_id if previous else ''
        version_filter = str(self.version.currentData() or '')
        if str(self.version_qa_filter.currentData() or '') == 'not_declared':
            version_filter = ''
        matching = filter_work_rows(
            self._projected, version=version_filter,
            severity=str(self.severity.currentData() or ''),
            source=str(self.source.currentData() or ''), query=self.search.text())
        matching = filter_version_rows(
            matching, self._version_audit,
            version=str(self.version.currentData() or ''),
            state=str(self.version_qa_filter.currentData() or ''))
        matching = filter_metadata_rows(
            matching, self._metadata_audit,
            version=str(self.version.currentData() or ''),
            state=str(self.metadata_filter.currentData() or ''))
        selected_mapping = str(self.mapping.currentData() or '')
        source_problems = {'source_unavailable', 'source_not_found',
                           'source_xml_conflict', 'expression_incomplete'}
        self._visible_rows = tuple(item for item in matching if (
            not selected_mapping
            or (selected_mapping == 'source_problem' and
                self._source_audit.get(item['row'].test_id, {}).get('status') in source_problems)
            or self._source_audit.get(item['row'].test_id, {}).get('status') == selected_mapping
        ))
        self.table.blockSignals(True)
        try:
            self.table.clear()
            selected = None
            for position, item in enumerate(self._visible_rows):
                row = item['row']
                entry = QTreeWidgetItem((
                    _LABELS.get(item['severity'], item['severity']), row.legacy_id,
                    row.test_id, row.name, row.source_xml, row.scope,
                    ', '.join(row.versions), self._version_qa_label(row.test_id),
                ))
                entry.setData(0, Qt.ItemDataRole.UserRole, position)
                for col in range(entry.columnCount()):
                    entry.setToolTip(col, entry.text(col))
                self.table.addTopLevelItem(entry)
                if row.test_id == previous_id:
                    selected = entry
            if selected is None and self.table.topLevelItemCount():
                selected = self.table.topLevelItem(0)
            if selected is not None:
                self.table.setCurrentItem(selected)
        finally:
            self.table.blockSignals(False)
        counts = {}
        for item in self._visible_rows:
            status = item['severity']
            counts[status] = counts.get(status, 0) + 1
        actual = catalogue_summary(self._rows)
        self.summary.setText(
            f"{len(self._visible_rows)} av {actual['tests']} testdefinisjoner | "
            + '  |  '.join(f'{key}: {count}' for key, count in sorted(counts.items()))
            + f'\nKDRS-kildesjekk: {self._legacy["source_unique_job_ids"]} ulike jobb-ID-er, '
              f'{len(self._legacy["not_in_dwm_catalog"])} mangler i DWM. '
              f'{actual["version_unverified"]} katalogtester har uverifisert versjonsgrunnlag. '
              'KDRS-ID-dekning er ikke full kravdekning eller formelparitet.'
              '\nVersjons-QA: Deklarert anvendelse er ikke dokumentert normoppfyllelse. '
              'Status og kildebevis vises per valgt Noark-versjon.')
        self._selection_changed()
        self._render_metadata()
        self._render_semantics()
        self._render_coverage()
        self._render_a8()

    def _render_metadata(self):
        """Browse ALL registered M-fields / requirements, including without XPath."""
        version = str(self.version.currentData() or '')
        query = self.search.text().strip().casefold()
        entries = []
        for v in ((version,) if version else VERSIONS):
            summary = self._metadata_audit['versions'][v]
            for meta in summary['metadata']:
                entries.append(meta)
            for req in summary['requirements']:
                entries.append(req)
        if query:
            entries = [entry for entry in entries if query in ' '.join(str(entry.get(k, ''))
                       for k in ('metadata_id', 'requirement_id', 'name', 'summary',
                                 'noark_version', 'xml_field_name')).casefold()]
        previous = self.metadata_table.currentItem()
        previous_key = previous.data(0, Qt.ItemDataRole.UserRole) if previous else None
        self._metadata_entries = entries
        self.metadata_table.blockSignals(True)
        try:
            self.metadata_table.clear()
            chosen = None
            for i, entry in enumerate(entries):
                is_meta = entry['type'] == 'metadata'
                label = entry['metadata_id'] if is_meta else entry['requirement_id']
                title = entry['name'] if is_meta else entry['summary']
                candidates = entry['xpath_candidates']
                state = (entry['mapping_state'] if is_meta else entry['source_status'])
                row = QTreeWidgetItem((
                    'Metadata' if is_meta else 'Krav', label, title,
                    entry['noark_version'], str(len(candidates)), state))
                row.setData(0, Qt.ItemDataRole.UserRole, (entry['noark_version'], label))
                row.setData(0, int(Qt.ItemDataRole.UserRole) + 1, i)
                for col in range(row.columnCount()):
                    row.setToolTip(col, row.text(col))
                self.metadata_table.addTopLevelItem(row)
                if previous_key == (entry['noark_version'], label):
                    chosen = row
            if chosen is None and self.metadata_table.topLevelItemCount():
                chosen = self.metadata_table.topLevelItem(0)
            if chosen is not None:
                self.metadata_table.setCurrentItem(chosen)
        finally:
            self.metadata_table.blockSignals(False)
        self.metadata_summary.setText(
            f'{len(entries)} registrerte elementer vist. '
            'Tomt/manglende kravregister = ennå ikke kildekartlagt, ikke ingen krav. '
            'Ingen godkjenning beregnes her.')
        self._metadata_selection_changed()

    def _metadata_selection_changed(self):
        selected = self.metadata_table.currentItem()
        if selected is None:
            self.metadata_detail.clear()
            return
        index = selected.data(0, int(Qt.ItemDataRole.UserRole) + 1)
        if not isinstance(index, int) or not (0 <= index < len(self._metadata_entries)):
            self.metadata_detail.clear()
            return
        entry = self._metadata_entries[index]
        self.metadata_detail.setPlainText(
            'METADATA / NORMATIVT KRAV - KILDEKOBLING (a4)\n'
            'Kun katalog- og kildereferanser, ikke kontrollutfall.\n\n'
            + _preview_json(entry, limit=75_000))

    def _choose_coverage_report(self):
        filename, _selected = QFileDialog.getOpenFileName(
            self, 'Velg generert a7 QA-matrise', '', 'JSON (*.json)')
        if not filename:
            return
        try:
            path = Path(filename)
            if not path.is_file() or path.stat().st_size > 20_000_000:
                raise ValueError('Rapporten mangler eller er for stor.')
            loaded = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(loaded, dict) or loaded.get('report_type') != A7_MATRIX_REPORT_TYPE:
                raise ValueError('Ikke en gjenkjennelig a7-kildematrise.')
            if loaded.get('noark_conformance_verified') is not False:
                raise ValueError('Rapportens normative status er ukjent eller ugyldig.')
            if set(loaded.get('versions', {})) != set(VERSIONS):
                raise ValueError('Rapporten mangler en av de tre Noark-versjonene.')
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, 'QA-matrise', str(exc))
            return
        self._coverage_report = loaded
        self._render_coverage()

    def _render_coverage(self, *_unused):
        """Filter saved QA evidence without rewriting, executing or approving it."""
        self.coverage_table.blockSignals(True)
        try:
            self.coverage_table.clear()
            self._coverage_entries = []
            if not self._coverage_report:
                self.coverage_summary.setText(
                    'Ingen a7-matrise lastet. Generer den fra lokal digital-archive-workflow '
                    'med a7 CLI og velg noark5-a7-matrix.json. Ingen Noark-krav er automatisk godkjent.')
                self.coverage_detail.clear()
                return
            version = str(self.version.currentData() or '')
            status = str(self.coverage_status.currentData() or '')
            search = self.search.text().strip().casefold()
            entries = filter_matrix_rows(
                self._coverage_report, version=version, severity=status, query=search)
            self._coverage_entries = entries
            for idx, entry in enumerate(entries):
                item = QTreeWidgetItem((str(entry['severity']), str(entry['version']),
                    str(entry['kind']), str(entry['id']), str(entry['name']),
                    str(entry['candidate_count'])))
                item.setData(0, Qt.ItemDataRole.UserRole, idx)
                for column in range(item.columnCount()):
                    item.setToolTip(column, item.text(column))
                self.coverage_table.addTopLevelItem(item)
            if self.coverage_table.topLevelItemCount():
                self.coverage_table.setCurrentItem(self.coverage_table.topLevelItem(0))
            self.coverage_summary.setText(
                f'{len(entries)} matrise- og QA-rader vist. '
                f"Kildecommit: {self._coverage_report.get('source_checkout_commit') or 'ukjent'}. "
                'Status gjelder kildesporing, ikke arkivuttrekkets valideringsutfall. '
                'Alle normative krav er fortsatt under kartlegging.')
        finally:
            self.coverage_table.blockSignals(False)
        self._coverage_selection_changed()

    def _coverage_selection_changed(self):
        selected = self.coverage_table.currentItem()
        position = selected.data(0, Qt.ItemDataRole.UserRole) if selected else None
        if not isinstance(position, int) or position < 0 or position >= len(self._coverage_entries):
            self.coverage_detail.clear()
            return
        entry = self._coverage_entries[position]
        self.coverage_detail.setPlainText(
            'KILDE-/KRAVMATRISE: TEKNISK QA, IKKE NORMATIV GODKJENNING\n\n'
            + _preview_json(entry['detail'], limit=75_000))

    def _render_semantics(self):
        """Show entire version-aware meaning catalogue, not Work's raw data."""
        version = str(self.version.currentData() or '')
        query = self.search.text().strip().casefold()
        aliases_by_id = {}
        for alias in self._semantic_registry.get('aliases', []):
            aliases_by_id.setdefault(alias['concept_id'], []).append(alias)
        rows = []
        for concept in self._semantic_registry['concepts']:
            aliases = aliases_by_id.get(concept['concept_id'], [])
            search_text = ' '.join([
                concept['metadata_id'], concept['concept_id'], concept['preferred_label'],
                self._semantic_registry['historical_xsd_type_names_3_1_4_0'].get(concept['metadata_id'], ''),
                *(a['raw_value'] for a in aliases),
            ]).casefold()
            if query and query not in search_text:
                continue
            literals = concept['exact_xsd_literals']
            if version == '5.0':
                status = 'Ingen fast enumeration i XSD-type'
            elif version:
                status = 'Eksakt XSD-literal' if literals.get(version) else 'Ikke opplistet i denne XSD'
            else:
                present = [v for v in ('3.1', '4.0') if literals.get(v)]
                status = 'XSD v' + ', '.join(present) if present else 'Bare QA-lokal'
            rows.append({'concept': concept, 'aliases': aliases, 'xsd_status': status})
        previous = self.semantic_table.currentItem()
        previous_id = previous.data(0, Qt.ItemDataRole.UserRole) if previous else None
        self._semantic_entries = rows
        self.semantic_table.blockSignals(True)
        try:
            self.semantic_table.clear()
            selection = None
            for index, row in enumerate(rows):
                concept = row['concept']
                item = QTreeWidgetItem((
                    concept['metadata_id'], concept['concept_id'],
                    concept['preferred_label'], row['xsd_status'], str(len(row['aliases']))))
                item.setData(0, Qt.ItemDataRole.UserRole, concept['concept_id'])
                item.setData(0, int(Qt.ItemDataRole.UserRole) + 1, index)
                for col in range(item.columnCount()):
                    item.setToolTip(col, item.text(col))
                self.semantic_table.addTopLevelItem(item)
                if concept['concept_id'] == previous_id:
                    selection = item
            if selection is None and self.semantic_table.topLevelItemCount():
                selection = self.semantic_table.topLevelItem(0)
            if selection is not None:
                self.semantic_table.setCurrentItem(selection)
        finally:
            self.semantic_table.blockSignals(False)
        candidates = sum(1 for row in rows for a in row['aliases']
                         if a['status'] == 'proposal_requires_qa')
        self.semantic_summary.setText(
            f'{len(rows)} stabile menings-ID-er vist | {candidates} aliasforslag krever QA. '
            'Råverditellinger hentes fra faktisk kontrollresultat, ikke dette registeret. '
            'Et menings-ID-treff gir aldri automatisk XSD-godkjenning.')
        self._semantic_selection_changed()

    def _semantic_selection_changed(self):
        selected = self.semantic_table.currentItem()
        if selected is None:
            self.semantic_detail.clear()
            return
        index = selected.data(0, int(Qt.ItemDataRole.UserRole) + 1)
        if not isinstance(index, int) or not (0 <= index < len(self._semantic_entries)):
            self.semantic_detail.clear()
            return
        self.semantic_detail.setPlainText(
            'MENING / SPRÅKLIG VARIANT – KILDE OG QA (a6)\n'
            'Betydningskobling er IKKE XML/XSD-validitet eller normativ godkjenning.\n\n'
            + _preview_json(self._semantic_entries[index], limit=75_000))

    def _version_qa_label(self, test_id):
        item = self._version_audit['tests'].get(test_id, {}).get('by_version', {})
        version = str(self.version.currentData() or '')
        if version:
            status = str(item.get(version, {}).get('status') or 'ukjent')
            return _VERSION_LABELS.get(status, status)
        summary = [item[v].get('status') for v in VERSIONS if v in item]
        if any(value == 'reference_conflict' for value in summary):
            return 'Referansekonflikt'
        if any(value == 'needs_version_qa' for value in summary):
            return 'Krever kilde-QA'
        if any(value == 'registry_unavailable' for value in summary):
            return 'Register mangler'
        return ', '.join(sorted(set(summary)))[:55]

    def _current_record(self):
        item = self.table.currentItem()
        if item is None:
            return None
        i = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(i, int) and 0 <= i < len(self._visible_rows):
            return self._visible_rows[i]
        return None

    def _selection_changed(self):
        item = self._current_record()
        self.open_result.setEnabled(bool(item and item['result']))
        if item is None:
            self.detail.clear()
            return
        row = item['row']
        source_audit = self._source_audit.get(row.test_id, {})
        version_qa = self._version_audit['tests'].get(row.test_id, {}).get('by_version', {})
        selected_version = str(self.version.currentData() or '')
        shown_versions = (selected_version,) if selected_version else VERSIONS
        text = [
            row.name, '=' * 60,
            'DWM-test: ' + row.test_id,
            'KDRS original jobb-ID: ' + row.legacy_id,
            'Noark-punkt: ' + (row.test_point or 'Ikke oppgitt'),
            'Status: ' + _LABELS.get(item['severity'], item['severity']),
            'Kilde-XML: ' + row.source_xml,
            'Scope: ' + row.scope,
            'Katalog-oppgitt versjoner: ' + ', '.join(row.versions),
            'Versjonsgrunnlag: ' + row.version_basis,
            'Definisjonsstatus: ' + row.definition_status,
            'Kj\u00f8reprofil: ' + (row.lifecycle_role or 'ordin\u00e6r katalogtest'),
            '', 'VURDERING / BESKJEDER',
            *('  - ' + text for text in item['reasons']),
            '', f'DEKLARERTE XPATH-UTTRYKK ({len(row.paths)})',
            *(f'{i}. {path}' for i, path in enumerate(row.paths, 1)),
            '', 'ORIGINAL KDRS QUERY / SAXON (ikke evaluert i DWM)',
            legacy_source_expression(row),
            '', 'KDRS -> DWM: KILDESPORING (a2, ikke semantisk fasit)',
            'Koblingsstatus: ' + str(source_audit.get('status') or 'Ukjent'),
            'Referanse SHA-256: ' + str(source_audit.get('reference_sha256') or 'Ikke tilgjengelig'),
            'Originalt uttrykk SHA-256: ' + str(source_audit.get('original_expression_sha256') or 'Ikke tilgjengelig'),
            'Original XML-kilde: ' + str(source_audit.get('original_source_xml') or 'Ikke oppgitt'),
            *(f"  - {m['scope']}/{m['id']}: {m['fragment_status']} : {m['expression']}"
              for m in source_audit.get('metrics', [])),
            'Tekstlige fragmenttreff er IKKE en testkjøring av KDRS/Saxon.',
            '', 'NOARK-VERSJON: KILDEKONTROLL (a3, ikke normativ godkjenning)',
            *(_preview_json(version_qa.get(v, {}), limit=12_000) for v in shown_versions),
            'En kobling til et verdi-sett dokumenterer bare referansen, ikke at feltet er validert.',
            '', 'METADATA OG KRAV: MULIGE KOBLINGER (a4)',
            *(_preview_json(self._metadata_audit['tests'].get(row.test_id, {})
                            .get('by_version', {}).get(v, {}), limit=8_000)
              for v in shown_versions),
            'XPath-omtale og verdi-settreferanse er ikke en faglig M-feltvalidering.',
            '', 'STANDARDVERDIREFERANSER',
            *('  - ' + value for value in row.standard_checks),
        ]
        if not row.standard_checks:
            text.append('Ingen registrert for denne testen.')
        if item['index_entry']:
            text.extend(('', 'LAGRET KJ\u00d8RING', 'Indeks: ' + item['index_path'],
                         _preview_json(item['index_entry'])))
        if item['result']:
            text.extend(('', 'LAGRET TESTRESULTAT (avkortes ved store data)',
                         _preview_json(item['result'])))
        else:
            text.extend(('', item['run_note'] or 'Ingen lesbar resultatevidens.'))
        text.extend(('', 'MERKNAD',
                     'Deklarert XPath er ikke det samme som verifisert identisk '
                     'KDRS/Saxon-semantikk. Funksjonskrav kan ikke automatisk '
                     'etterprøves ved et statisk uttrekk.'))
        self.detail.setPlainText('\n'.join(text))
        self.detail.moveCursor(QTextCursor.MoveOperation.Start)

    def _open_result(self):
        item = self._current_record()
        if not item or not item['index_entry'] or not self._current_shot():
            return
        name = str(item['index_entry'].get('file') or '').replace('\\', '/')
        rel = Path(name)
        if rel.parts[:1] != ('results',) or len(rel.parts) != 2 or rel.suffix != '.json':
            return
        index = Path(item['index_path'])
        path = index.parent / rel
        if _read_json(path, within=self._current_shot().job.work, limit=3_000_000) is None:
            QMessageBox.warning(self, 'Testresultat', 'Filen er ikke tilgjengelig eller ligger utenfor Work.')
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _choose_a8_report(self):
        filename, _selected = QFileDialog.getOpenFileName(
            self,'Velg lokal Noark 5 a8 QA-rapport','','JSON (*.json)')
        if not filename:
            return
        try:
            path=Path(filename)
            if not path.is_file() or path.stat().st_size > 24_000_000:
                raise ValueError('Rapportfilen mangler eller overstiger 24 MB.')
            loaded=json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(loaded,dict) or loaded.get('report_type')!=A8_REVIEW_REPORT_TYPE:
                raise ValueError('Ikke en gjenkjennelig a8 QA-rapport.')
            if loaded.get('normative_requirements_approved') is not False:
                raise ValueError('Rapportens normative status er uavklart.')
            if set(loaded.get('versions',{})) != set(VERSIONS):
                raise ValueError('Rapporten mangler en Noark-versjon.')
            if not isinstance(loaded.get('candidate_rows'),list):
                raise ValueError('Rapporten mangler kravkandidater.')
        except (OSError,UnicodeError,ValueError,TypeError) as exc:
            QMessageBox.warning(self,'Krav-/KDRS-review',str(exc))
            return
        self._a8_report=loaded
        self._render_a8()

    def _render_a8(self,*_unused):
        self.a8_table.blockSignals(True)
        self.a8_kdrs_table.blockSignals(True)
        try:
            self.a8_table.clear()
            self.a8_kdrs_table.clear()
            self._a8_entries=[]
            self._a8_kdrs_entries=[]
            if not self._a8_report:
                self.a8_summary.setText('Ingen a8-rapport lastet. Generer den fra a7-matrisen '
                                        'og den lokale Noark-kildesamlingen.')
                self.a8_detail.clear()
                self.a8_kdrs_detail.clear()
                return
            version=str(self.version.currentData() or '')
            status=str(self.a8_status.currentData() or '')
            origin=str(self.a8_origin.currentData() or '')
            query=self.search.text()
            rows=filter_review_rows(self._a8_report,version=version,
                                    severity=status,origin=origin,query=query)
            self._a8_entries=rows
            for i,row in enumerate(rows):
                number=row.get('number') or row.get('registered_id') or ''
                item=QTreeWidgetItem((str(row.get('qa_severity') or ''),
                    str(row.get('noark_version') or ''),str(number),
                    str(row.get('origin') or ''),str(row.get('text') or '')[:240],
                    str(len(row.get('xpath_lexical_candidates') or []))))
                item.setData(0,Qt.ItemDataRole.UserRole,i)
                for col in range(item.columnCount()):
                    item.setToolTip(col,item.text(col))
                self.a8_table.addTopLevelItem(item)
            if self.a8_table.topLevelItemCount():
                self.a8_table.setCurrentItem(self.a8_table.topLevelItem(0))
            audit=self._a8_report.get('kdrs_audit') or {}
            kdrs=[r for r in audit.get('tests',[])
                  if not status or r.get('qa_severity')==status]
            if query.strip():
                q=query.casefold().strip()
                kdrs=[r for r in kdrs if q in ' '.join(str(r.get(f) or '')
                      for f in ('test_id','legacy_id','execution_kind','source_xml')).casefold()]
            self._a8_kdrs_entries=kdrs
            for i,row in enumerate(kdrs):
                item=QTreeWidgetItem((str(row.get('qa_severity') or ''),
                    str(row.get('legacy_id') or ''),str(row.get('test_id') or ''),
                    str(row.get('execution_kind') or ''),
                    str(row.get('dispatch_verdict') or '')))
                item.setData(0,Qt.ItemDataRole.UserRole,i)
                self.a8_kdrs_table.addTopLevelItem(item)
            if self.a8_kdrs_table.topLevelItemCount():
                self.a8_kdrs_table.setCurrentItem(self.a8_kdrs_table.topLevelItem(0))
            self.a8_summary.setText(
                f'{len(rows)} krav-/tallkandidater og {len(kdrs)} tekniske KDRS-rader vist. '
                f"Kildecommit: {self._a8_report.get('source_checkout_commit') or 'ukjent'}. "
                'Rapporten verifiserer ikke normativ oppfyllelse eller KDRS/Saxon-paritet.')
        finally:
            self.a8_table.blockSignals(False)
            self.a8_kdrs_table.blockSignals(False)
        self._a8_selection_changed()
        self._a8_kdrs_selection_changed()

    def _a8_selection_changed(self):
        selected=self.a8_table.currentItem()
        index=selected.data(0,Qt.ItemDataRole.UserRole) if selected else None
        if not isinstance(index,int) or not 0 <= index < len(self._a8_entries):
            self.a8_detail.clear()
            return
        self.a8_detail.setPlainText(
            'KILDE-KANDIDAT / FAGLIG QA - a8\n'
            'Ikke et automatisk godkjent Noark 5-krav.\n\n'+
            _preview_json(self._a8_entries[index],limit=100_000))

    def _a8_kdrs_selection_changed(self):
        selected=self.a8_kdrs_table.currentItem()
        index=selected.data(0,Qt.ItemDataRole.UserRole) if selected else None
        if not isinstance(index,int) or not 0 <= index < len(self._a8_kdrs_entries):
            self.a8_kdrs_detail.clear()
            return
        self.a8_kdrs_detail.setPlainText(
            'KDRS STANDARD / U1 / U2 - DISPATCH OG KILDEKOBLING - a8\n'
            'Teknisk dispatch er ikke bevis på Saxon/lxml-resultatlikhet.\n\n'+
            _preview_json(self._a8_kdrs_entries[index],limit=100_000))

    def _choose_schema(self):
        folder = QFileDialog.getExistingDirectory(
            self, 'Velg digital-archive-workflow eller Noark 5-kildemappe',
            str(self._schema_root or Path.home()))
        if folder:
            self._schema_root = Path(folder)
            self._refresh_schema_summary()
            self._filter()

    def _refresh_schema_summary(self):
        if self._schema_root is None:
            self._schema = None
            self.schema_info.setText('XSD: kilderepoet er ikke koblet til lokalt. '
                                     'XPath-katalogen er tilgjengelig uansett.')
            return
        self._schema = schema_inventory(self._schema_root)
        self._version_audit = build_version_audit(rows=self._rows, schema_root=self._schema_root)
        available = sum(len(x) for x in self._schema['versions'].values())
        self.schema_info.setText(
            f'XSD: {available}/15 skjemaer i lokalt kildebibliotek. '
            f'Mangler: {len(self._schema["missing"])}. '
            'XSD-validitet og XPath-observasjoner holdes atskilt.')

    def _view_schema(self):
        if self._schema is None:
            QMessageBox.information(self, 'XSD-dekning',
                                    'Velg en lokal klone av digital-archive-workflow for XSD-kartlegging.')
            return
        report = schema_lexical_coverage(self._schema, self._rows)
        printable = {'root': self._schema['root'], 'missing': self._schema['missing'],
                     'errors': self._schema['errors'], 'declarative_mention': report,
                     'method_note': 'Dette er tekstlig navnetreff i deklarert XPath, IKKE normativ dekning.'}
        dialog = QDialog(self)
        dialog.setWindowTitle('XSD 3.1 / 4.0 / 5.0 - kartlegging')
        dialog.resize(1050, 740)
        layout = QVBoxLayout(dialog)
        display = QPlainTextEdit(dialog)
        display.setReadOnly(True)
        display.setPlainText(_preview_json(printable, limit=300_000))
        layout.addWidget(display)
        button = QPushButton('Lukk', dialog)
        button.clicked.connect(dialog.accept)
        layout.addWidget(button)
        dialog.exec()


def install_xpath_catalog_link(viewer):
    """One button in existing Oversikt: mirror the M300 drilldown workflow."""
    if getattr(viewer, '_v021_xpath_audit_installed', False):
        return
    viewer._v021_xpath_audit_installed = True
    page = viewer._pages['Oversikt']
    row = QHBoxLayout()
    note = QLabel('Noark 5 XPath: KDRS Standard / U1 / U2, versjonsdekning og lagret Work.', page)
    note.setWordWrap(True)
    row.addWidget(note, 1)
    button = QPushButton('Vis alle XPath-kontroller...', page)
    button.setToolTip('Filter: FEIL, WARNING, NOTE, kilde mangler og ikke kjørt.')
    button.clicked.connect(lambda: XPathCoverageDialog(viewer).exec())
    row.addWidget(button)
    page.layout().insertLayout(0, row)
    viewer._v021_xpath_audit_button = button
