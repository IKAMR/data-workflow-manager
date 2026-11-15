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
