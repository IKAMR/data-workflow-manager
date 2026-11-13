"""Standard-value drilldown from Resultatvisninger / Oversikt.

Saved depot-report findings are the entrypoint. User-requested XML evidence
is read-only; explicitly exported fragments go only to the approved job Work.
No XPath/system ID is invented when the report lacks it.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QFileDialog, QComboBox, QPlainTextEdit,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QHeaderView, QCheckBox,
)

from app.xml_value_evidence_v0114_a3 import (
    find_xml_values, source_xml_for_work, source_xpath_for_finding, describe_xml_source,
)
from concurrent.futures import ThreadPoolExecutor

from gui_qt.experience_assessment_v0114_a7 import ExperienceAssessmentDialog
from app.noark_standard_reference_v0114_a4 import reference_for_finding, reference_versions
from app.noark_xsd_rules_v0114_a6 import comparison_rows, describe_constraint
from app.noark_xsd_local_evidence_v0114_a6 import save_xsd_evidence, work_from_report
from app.noark_xsd_version_v0114_a5 import (
    inspect_report_version, inspect_source_version, comparison_label,
)
from app.noark_extract_display_v0114_a7 import extract_display_name
from app.xml_context_v0114_a8 import inspect_xml_context, readable_xml, save_xml_extract
from gui_qt.view_display_preferences import word_wrap_enabled, save_word_wrap_enabled, apply_word_wrap
from app.standard_value_findings_v0114_a2 import (
    findings_from_snapshots, source_location_present,
)


class StandardValuesDialog(QDialog):
    def __init__(self, parent, findings):
        super().__init__(parent)
        self.setWindowTitle('Standardverdikontroller – ekstra observerte verdier')
        self.setMinimumSize(900, 600)
        # Use the available geometry of the screen containing the parent.
        # A fixed 1040x670 dialog clips both the findings and the details.
        parent_center = parent.mapToGlobal(parent.rect().center()) if parent is not None else None
        screen = QGuiApplication.screenAt(parent_center) if parent_center is not None else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            target_width = min(1550, max(900, int(area.width() * 0.92)))
            target_height = min(1100, max(600, int(area.height() * 0.92)))
            self.resize(min(target_width, area.width()), min(target_height, area.height()))
        else:
            self.resize(1250, 850)
        # Group duplicates by test/field and present identified 5.0 before historic 4.0/3.1.
        # Missing/unknown versions are last, without pretending an extract is v5.0.
        self._findings = tuple(sorted(findings, key=lambda f: (
            f.job_name, f.test_id, f.field,
            {'5.0': 0, '4.0': 1, '3.1': 2}.get(str(f.version), 3))))
        self._version_cache = {}
        layout = QVBoxLayout(self)
        info = QLabel(f'{len(findings)} kontroller med ekstra observerte verdier. '
                      'Tallet gjelder kontroller, ikke unike verdier.')
        info.setWordWrap(True)
        layout.addWidget(info)
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.table = QTableWidget(len(findings), 7, splitter)
        self.table.setHorizontalHeaderLabels(('Uttrekk', 'M-ID', 'Test-ID', 'Kontrollert felt',
                                              'Regelversjon', 'Forekomster', 'XML-kilde'))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(word_wrap_enabled())
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(1, 65)
        self.table.setColumnWidth(2, 95)
        self.table.setColumnWidth(3, 170)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 105)
        details = QWidget(splitter)
        detail_layout = QVBoxLayout(details)
        self.detail_title = QLabel('Velg en kontroll for å se lagret evidens.')
        detail_layout.addWidget(self.detail_title)
        self.detail = QTreeWidget(details)
        self.detail.setHeaderLabels(('Opplysning', 'Lagret verdi'))
        self.detail.setRootIsDecorated(True)
        self.detail.setAlternatingRowColors(True)
        self.detail.setWordWrap(word_wrap_enabled())
        self.detail.setColumnWidth(0, 230)
        detail_layout.addWidget(self.detail)
        # Give the findings enough height for all eight rows while preserving
        # the majority of the window for the expanded evidence tree.
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([255, max(480, self.height() - 365)])
        layout.addWidget(splitter, 1)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 6, 0, 4)
        bottom.setSpacing(7)
        self.source_notice = QLabel('Noark 3.1, 4.0 og 5.0 er SAMMENLIGNINGSVERSJONER. Uttrekkets faktiske versjon er ikke verifisert her.')
        self.source_notice.setWordWrap(True)
        bottom.addWidget(self.source_notice, 1)
        self.find_xml = QPushButton('Vis XML-forekomster…')
        self.find_xml.clicked.connect(self._show_xml)
        bottom.addWidget(self.find_xml)
        self.reference_button = QPushButton('Noark-referanse…')
        self.reference_button.setToolTip('Lokal metadatakode, versjonert verdiliste, XPath og referanse til Noark 5-kilder')
        self.reference_button.clicked.connect(self._show_reference)
        bottom.addWidget(self.reference_button)
        self.version_button = QPushButton('XSD / Noark-versjon…')
        self.version_button.setToolTip('Se XSD-versjonsattributt, endringshistorikk, SHA-256 og konflikter mot arkivuttrekk.xml')
        self.version_button.clicked.connect(self._show_version_evidence)
        bottom.addWidget(self.version_button)
        self.experience_button = QPushButton('Erfaringsvurdering…')
        self.experience_button.setToolTip('Kjente funn, faglig vurderingsforslag og lokal lagring i Work')
        self.experience_button.clicked.connect(self._show_experience)
        bottom.addWidget(self.experience_button)
        self.open_report = QPushButton('Depotrapport')
        self.open_report.clicked.connect(self._open_report)
        bottom.addWidget(self.open_report)
        close = QPushButton('Lukk')
        close.clicked.connect(self.close)
        bottom.addWidget(close)
        layout.addLayout(bottom)
        self.table.setSortingEnabled(False)
        for row, finding in enumerate(self._findings):
            reference = reference_for_finding(finding.test_id, finding.field, finding.version)
            metadata_id = reference['metadata_id'] if reference else '–'
            cells = (extract_display_name(finding.job_name, finding.report_path), metadata_id, finding.test_id, finding.field,
                     finding.version or '–', str(finding.extra_total),
                     'Undersøk kilde')
            for col, cell in enumerate(cells):
                cell_item = QTableWidgetItem(cell)
                if col == 0:
                    cell_item.setData(Qt.ItemDataRole.UserRole, row)
                    cell_item.setToolTip(f'Jobbnavn: {finding.job_name}\nRapport: {finding.report_path or "Ikke oppgitt"}')
                if col == 5:
                    cell_item.setData(Qt.ItemDataRole.DisplayRole, int(finding.extra_total))
                self.table.setItem(row, col, cell_item)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._show_selected)
        if findings:
            self.table.selectRow(0)

    def _version_for(self, finding):
        key = str(finding.report_path or '')
        if key not in self._version_cache:
            self._version_cache[key] = inspect_report_version(finding.report_path)
        return self._version_cache[key]

    def _show_version_evidence(self):
        finding = self._current()
        if finding is None:
            return
        dialog = NoarkVersionEvidenceDialog(self, self._version_for(finding),
                                            rule_version=finding.version, report_path=finding.report_path)
        dialog.exec()

    def _current(self):
        # Sorting reorders Qt table rows but never the saved findings.
        cell = self.table.item(self.table.currentRow(), 0)
        index = cell.data(Qt.ItemDataRole.UserRole) if cell is not None else None
        return self._findings[index] if isinstance(index, int) and 0 <= index < len(self._findings) else None

    def _show_selected(self):
        item = self._current()
        self.detail.clear()
        if item is None:
            return
        self.detail_title.setText(f'{item.test_id} · {item.field} · sammenlignet mot regelsett {item.version or "ukjent"}')
        def add(label, value):
            QTreeWidgetItem(self.detail, [label, str(value)])
        add('Test-ID', item.test_id)
        add('Noark-punkt', item.test_point or 'Ikke oppgitt')
        add('Kontrollert felt', item.field)
        ref = reference_for_finding(item.test_id, item.field, item.version)
        if ref:
            add('Noark metadata-ID', ref['metadata_id'] + ' – ' + ref['name'])
            add('Verdiregister', ref['value_set_id'])
            add('Standardkilde', ref['registry_file'])
            add('Kildeelement', ref['source_xml'] + ' · ' + (ref['xpath'] or 'XPath ikke angitt'))
        else:
            add('Noark metadata-ID', 'Ingen dokumentert kobling i testkatalogen')
        add('Sammenlignet mot regelversjon', item.version or 'Ikke oppgitt')
        evidence = self._version_for(item)
        add('Uttrekkets Noark-versjon (XSD)', evidence.display)
        add('Regelversjonsstatus', comparison_label(evidence, item.version))
        if ref and evidence.version and evidence.status == 'confirmed':
            historical = comparison_rows(ref['metadata_id'], evidence.version, item.extra)
            group = QTreeWidgetItem(self.detail, ['XSD-feltregler: gjeldende, deretter bakover', ''])
            for rule in historical:
                label = 'Gjeldende' if rule['current'] else 'Historisk'
                sub = QTreeWidgetItem(group, [f"Noark 5 v{rule['version']} ({label})", rule['description']])
                QTreeWidgetItem(sub, ['Referanse-XSD', rule['source']])
                for obs in rule['observations']:
                    QTreeWidgetItem(sub, [obs['value'], obs['explanation']])
                if rule['restriction'] == 'enumeration':
                    for value in rule['values']:
                        QTreeWidgetItem(sub, ['Tillatt i XSD', value])
                sub.setExpanded(True)
            group.setExpanded(True)
        if evidence.addml_version:
            add('Oppgitt i arkivuttrekk.xml', 'v' + evidence.addml_version)
        for warning in evidence.warnings:
            add('Versjonsmerknad', warning)
        add('Status', 'Observasjon mot verdiregister; XSD-regel og faglig krav vurderes separat')
        add('Antall ekstra forekomster', item.extra_total)
        for title, data in (('Ekstra observerte verdier', item.extra),
                            ('Standardverdier (regelsett)', item.detail.get('standard_values')),
                            ('Observerte standardverdier (antall)', item.detail.get('standard_value_counts'))):
            group = QTreeWidgetItem(self.detail, [title, ''])
            if isinstance(data, dict):
                for key, count in data.items():
                    QTreeWidgetItem(group, [str(key), str(count)])
            elif isinstance(data, (list, tuple)):
                for value in data:
                    QTreeWidgetItem(group, [str(value), ''])
            elif data is not None:
                QTreeWidgetItem(group, ['Verdi', str(data)])
            else:
                QTreeWidgetItem(group, ['Ikke lagret i rapporten', ''])
            group.setExpanded(True)
        add('Kilde', str(item.report_path) if item.report_path else 'Ikke oppgitt')
        self.source_notice.setText(
            evidence.display + ' · ' + comparison_label(evidence, item.version)
            + ' · XML-oppslag er skrivebeskyttet.')
        self.reference_button.setEnabled(bool(ref))
        self.open_report.setEnabled(bool(item.report_path and item.report_path.is_file()))

    def _show_xml(self):
        """Read-only per-value source explorer; never infer the extraction version."""
        finding = self._current()
        if finding is None or not finding.extra:
            return
        work = finding.report_path
        if work is not None:
            # The saved report is always somewhere underneath Work.
            for parent in work.parents:
                if (parent / 'job.json').is_file():
                    work = parent
                    break
        if work is None or not (work / 'job.json').is_file():
            work = None
        candidate = source_xml_for_work(work) if work else None
        if candidate is None:
            path, _ = QFileDialog.getOpenFileName(
                self, 'Velg original arkivstruktur.xml (skrivebeskyttet)', '',
                'Noark 5 arkivstruktur (arkivstruktur.xml);;XML (*.xml)')
            if not path:
                return
            candidate = Path(path)
        # The report contains aggregate counts, not exact XML object links.
        # A fresh bounded lookup in the explicitly selected original is labelled as such.
        xml_dialog = XmlOccurrencesDialog(self, candidate, finding)
        xml_dialog.exec()


    def _show_reference(self):
        finding = self._current()
        if finding is None:
            return
        record = reference_for_finding(finding.test_id, finding.field, finding.version)
        if not record:
            QMessageBox.information(self, 'Noark-referanse',
                                    'Ingen dokumentert kobling mellom denne kontrollen og metadatakatalogen.')
            return
        dialog = NoarkMetadataReferenceDialog(self, finding, record)
        dialog.exec()

    def _show_experience(self):
        finding = self._current()
        if finding is None:
            return
        record = reference_for_finding(finding.test_id, finding.field, finding.version)
        if not record:
            QMessageBox.information(self, 'Erfaringsvurdering', 'Ingen dokumentert metadata-ID for denne kontrollen.')
            return
        dialog = ExperienceAssessmentDialog(self, finding, self._version_for(finding), record['metadata_id'])
        dialog.exec()

    def _open_report(self):
        item = self._current()
        if item is None or not item.report_path or not item.report_path.is_file():
            QMessageBox.information(self, 'Depotrapport', 'Lagret depotrapport er ikke tilgjengelig.')
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(item.report_path)))


class NoarkVersionEvidenceDialog(QDialog):
    """Show exact version evidence, without guessing from a loose XSD filename."""

    def __init__(self, parent, evidence, *, rule_version=None, report_path=None):
        super().__init__(parent)
        self.setWindowTitle('Noark-versjon – XSD-kildegrunnlag')
        self.resize(920, 560)
        self.setMinimumSize(650, 400)
        self._rule_version = rule_version
        self._report_path = report_path
        self._evidence = evidence
        body = QVBoxLayout(self)
        self.heading = QLabel()
        self.heading.setWordWrap(True)
        body.addWidget(self.heading)
        self.details = QTreeWidget(self)
        self.details.setWordWrap(word_wrap_enabled())
        self.details.setHeaderLabels(('Kilde / egenskap', 'Verdi'))
        self.details.setColumnWidth(0, 285)
        self.details.setAlternatingRowColors(True)
        body.addWidget(self.details, 1)
        actions = QHBoxLayout()
        self.choose = QPushButton('Velg Source for undersøkelse…')
        self.choose.setToolTip('Velg original uttrekksmappe manuelt; DWM endrer ingen kildefiler.')
        self.choose.clicked.connect(self._choose_source)
        actions.addWidget(self.choose)
        self.save_evidence = QPushButton('Lagre XSD-evidens i Work…')
        self.save_evidence.setToolTip('Lagrer kun lokal XSD-identitet, proveniens og observasjoner i jobbens Work; endrer ikke Source')
        self.save_evidence.clicked.connect(self._save_evidence)
        actions.addWidget(self.save_evidence)
        actions.addStretch(1)
        close = QPushButton('Lukk')
        close.clicked.connect(self.close)
        actions.addWidget(close)
        body.addLayout(actions)
        self._render()

    def _choose_source(self):
        folder = QFileDialog.getExistingDirectory(
            self, 'Velg original Source-mappe (skrivebeskyttet)',
            str(self._evidence.source or ''))
        if folder:
            self._evidence = inspect_source_version(Path(folder))
            self._render()

    def _save_evidence(self):
        work = work_from_report(self._report_path)
        if work is None:
            QMessageBox.warning(self, 'Lagre XSD-evidens',
                                'Ingen autoritativ Work-mappe (job.json) ble funnet for rapporten. Ingen filer er skrevet.')
            return
        try:
            target = save_xsd_evidence(self._evidence, work)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, 'Lagre XSD-evidens', str(exc))
            return
        QMessageBox.information(self, 'Lokal XSD-evidens lagret', str(target))

    def _render(self):
        evidence = self._evidence
        self.heading.setText(evidence.display + '\n' +
                             comparison_label(evidence, self._rule_version))
        self.details.clear()
        def add(k, v):
            QTreeWidgetItem(self.details, [str(k), str(v)])
        add('Source', evidence.source or 'Ikke tilgjengelig – velg Source')
        add('XSD-versjon', 'v' + evidence.version if evidence.version else 'Uavklart')
        add('Sammenlignet regelversjon', 'v' + str(self._rule_version) if self._rule_version else 'Ukjent')
        add('arkivuttrekk.xml', evidence.addml_path or 'Ikke funnet')
        add('Oppgitt Noark-versjon i ADDML', 'v' + evidence.addml_version if evidence.addml_version else 'Ikke verifisert')
        for rec in evidence.schemas:
            group = QTreeWidgetItem(self.details, [rec.path.name,
                                      ('v' + rec.version if rec.version else 'Ukjent XSD')])
            QTreeWidgetItem(group, ['Faktisk fil', str(rec.path)])
            QTreeWidgetItem(group, ['SHA-256', rec.digest or 'Ikke beregnet'])
            QTreeWidgetItem(group, ['XSD version-attributt', rec.declared_version or 'Ikke tilgjengelig'])
            QTreeWidgetItem(group, ['Identifikasjon', rec.status])
            if rec.maintenance_note:
                QTreeWidgetItem(group, ['Endringslogg / vedlikehold', rec.maintenance_note])
            if rec.reference:
                QTreeWidgetItem(group, ['Referanse (IKAMR)', rec.reference])
            group.setExpanded(True)
        for note in evidence.warnings:
            add('Merknad', note)
        add('Referansebibliotek', 'IKAMR/digital-archive-workflow · docs/kilder/noark/noark5')
        add('Vurdering', 'XSD version-attributt og konsistente skjemaer identifiserer standardversjonen; SHA-256 identifiserer filvarianten. Dette er ikke en XSD-validering.')


class NoarkMetadataReferenceDialog(QDialog):
    """Read-only locally sourced Noark value-set metadata, not a full specification."""

    def __init__(self, parent, finding, record):
        super().__init__(parent)
        self.setWindowTitle('Noark-metadata ' + record['metadata_id'] + ' – ' + record['name'])
        self.resize(840, 585)
        self.setMinimumSize(620, 410)
        self.record = record
        outer = QVBoxLayout(self)
        heading = QLabel(record['metadata_id'] + ' – ' + record['name'])
        heading.setStyleSheet('font-size: 17px; font-weight: 600;')
        outer.addWidget(heading)
        note = QLabel('Lokal referanse fra DWM sitt versjonerte standardverdiregister og XPath-katalog. '
                      'Dette er ikke den fullstendige Noark-spesifikasjonen eller en XSD-validering.')
        note.setWordWrap(True)
        outer.addWidget(note)
        ver_row = QHBoxLayout()
        ver_row.addWidget(QLabel('Sammenlign mot regelversjon:'))
        self.versions = QComboBox(self)
        for version in reference_versions(finding.test_id, finding.field):
            self.versions.addItem(version, version)
        index = self.versions.findData(finding.version)
        if index >= 0:
            self.versions.setCurrentIndex(index)
        self.versions.currentIndexChanged.connect(self._fill)
        ver_row.addWidget(self.versions)
        ver_row.addStretch(1)
        outer.addLayout(ver_row)
        self.info = QTreeWidget(self)
        self.info.setWordWrap(word_wrap_enabled())
        self.info.setHeaderLabels(('Opplysning', 'Verdi'))
        self.info.setColumnWidth(0, 235)
        self.info.setAlternatingRowColors(True)
        outer.addWidget(self.info, 1)
        footer = QHBoxLayout()
        self.location = QLabel('Kildegrunnlag: ' + record['registry_file'] + ' / ' + record['catalog_file'])
        self.location.setWordWrap(True)
        self.location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        footer.addWidget(self.location, 1)
        close = QPushButton('Lukk')
        close.clicked.connect(self.close)
        footer.addWidget(close)
        outer.addLayout(footer)
        self._fill()

    def _fill(self, _index=None):
        version = str(self.versions.currentData() or '')
        record = reference_for_finding(self.record['test_id'], self.record['field'], version)
        self.info.clear()
        if record is None:
            return
        def add(name, value):
            QTreeWidgetItem(self.info, [name, str(value)])
        add('Metadata-ID', record['metadata_id'])
        add('Metadatanavn', record['name'])
        add('Test-ID / Noark-punkt', record['test_id'] + ' / ' + (record['test_point'] or 'Ikke oppgitt'))
        add('Sammenlignet regelversjon', version)
        parent = self.parent()
        finding = parent._current() if hasattr(parent, '_current') else None
        evidence = parent._version_for(finding) if finding is not None and hasattr(parent, '_version_for') else None
        if evidence is not None:
            add('Uttrekkets faktiske versjon (XSD)', evidence.display)
            add('Sammenligningsstatus', comparison_label(evidence, version))
            if evidence.version and evidence.status == 'confirmed':
                history = comparison_rows(record['metadata_id'], evidence.version, {})
                historical = QTreeWidgetItem(self.info, ['XSD-feltregler (gjeldende → eldre)', ''])
                for constraint in history:
                    label = 'Gjeldende' if constraint['current'] else 'Historisk'
                    node = QTreeWidgetItem(historical, [f"v{constraint['version']} ({label})",
                                                             describe_constraint(constraint)])
                    QTreeWidgetItem(node, ['Kildeskjema', constraint['source']])
                    if constraint['restriction'] == 'enumeration':
                        for value in constraint['values']:
                            QTreeWidgetItem(node, ['XSD-tillatt verdi', value])
                historical.setExpanded(True)
        else:
            add('Uttrekkets faktiske versjon', 'Ikke bestemt av denne kontrollen')
        add('Regelregister-nøkkel', record['value_set_id'])
        add('Verdilisterolle', record['value_set_role'] or 'Ikke oppgitt')
        add('XML-kildefil', record['source_xml'])
        add('XPath fra testkatalog', record['xpath'] or 'Ikke dokumentert')
        xsd = record['xsd_note']
        add('XSD', xsd + ' Se dokumenterte historiske type-regler ovenfor når tilgjengelig.')
        values = QTreeWidgetItem(self.info, ['Registrerte standardverdier (' + str(len(record['values'])) + ')', ''])
        for value in record['values']:
            QTreeWidgetItem(values, [value, ''])
        values.setExpanded(True)
        add('Full spesifikasjonstekst', 'Ikke importert. Må dokumenteres fra autoritativ PDF/Word før visning.')
        add('Datakilde', record['registry_file'])
        add('Testdefinisjon', record['catalog_file'])


class XmlOccurrencesDialog(QDialog):
    """Source evidence with sort, adjustable panels and on-demand XML context."""

    def __init__(self, parent, xml_path, finding):
        super().__init__(parent)
        self.setWindowTitle('XML-evidens – ' + finding.test_id)
        parent_center = parent.mapToGlobal(parent.rect().center()) if parent is not None else None
        screen = QGuiApplication.screenAt(parent_center) if parent_center is not None else self.screen()
        area = screen.availableGeometry() if screen else None
        self.resize(min(1500, max(850, int(area.width() * .76))) if area else 1300,
                    min(980, max(620, int(area.height() * .90))) if area else 850)
        self.xml_path = Path(xml_path)
        self.finding = finding
        self.rows = ()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='dwm-xml-source')
        self._pending = None
        self._context_pending = None
        self._context_pending_xpath = None
        self._timer = None
        self._context_timer = None
        self._selected_xpath = None
        self._selected_context = None
        self._readable_mode = True
        outer = QVBoxLayout(self)
        info = QLabel('Kilde: ' + str(self.xml_path) + '\n'
                      'Noark-versjoner 3.1 / 4.0 / 5.0 er regelsett-sammenligninger, '
                      'ikke automatisk uttrekkets versjon.')
        info.setWordWrap(True)
        outer.addWidget(info)
        row = QHBoxLayout()
        row.addWidget(QLabel('Observert verdi:'))
        self.values = QComboBox(self)
        for value, amount in finding.extra.items():
            self.values.addItem(f'{value} ({amount} i lagret rapport)', value)
        row.addWidget(self.values, 1)
        self.search_button = QPushButton('Finn forekomster')
        self.search_button.clicked.connect(self._search)
        row.addWidget(self.search_button)
        outer.addLayout(row)
        self.message = QLabel('Velg Finn forekomster. Maks 25 konkrete treff; kildedata endres ikke.')
        self.message.setWordWrap(True)
        outer.addWidget(self.message)

        # Both separators are movable. The lower horizontal split provides
        # simultaneous structural context and the actual surrounding source XML.
        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.vertical_splitter.setChildrenCollapsible(False)
        self.results = QTableWidget(0, 4, self.vertical_splitter)
        self.results.setHorizontalHeaderLabels(('Linje', 'XML-sti (XPath)', 'System-ID', 'Verdi'))
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.setSortingEnabled(False)
        self.results.setAlternatingRowColors(True)
        self.results.setWordWrap(word_wrap_enabled())
        self.results.horizontalHeader().setSortIndicatorShown(False)
        self._sort_column = None
        self._sort_direction = None
        self.results.horizontalHeader().sectionClicked.connect(self._click_sort)
        self.results.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.results.setColumnWidth(0, 80)
        self.results.setColumnWidth(1, 650)
        self.results.setColumnWidth(2, 335)
        self.results.setColumnWidth(3, 270)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.lower_splitter = QSplitter(Qt.Orientation.Horizontal, self.vertical_splitter)
        self.lower_splitter.setChildrenCollapsible(False)
        self.structure = QTreeWidget(self.lower_splitter)
        self.structure.setHeaderLabels(('Arkivstruktur / forekomst', 'System-ID / tittel'))
        self.structure.setColumnWidth(0, 285)
        self.structure.setAlternatingRowColors(True)
        self.structure.setWordWrap(word_wrap_enabled())
        self.structure.setSortingEnabled(False)  # Preserve the source hierarchy.
        self.xml_text = QPlainTextEdit(self.lower_splitter)
        self.xml_text.setReadOnly(True)
        apply_word_wrap(word_wrap_enabled(), self.xml_text)
        self.xml_text.setPlaceholderText('Velg et treff for å undersøke XML-seksjonen i kontekst.')
        self.lower_splitter.setSizes([460, 750])
        self.vertical_splitter.setSizes([360, 440])
        outer.addWidget(self.vertical_splitter, 1)
        self.results.itemSelectionChanged.connect(self._selection_changed)
        bottom = QHBoxLayout()
        self.context_status = QLabel('Kontekst vises ved valg av treff; antall søsken beregnes der det kan dokumenteres.')
        self.context_status.setWordWrap(True)
        bottom.addWidget(self.context_status, 1)
        self.auto_layout_button = QPushButton('Autojuster visning')
        self.auto_layout_button.setToolTip('Tilpass vindu, panelskille og kolonnebredder til tilgjengelig skjermplass')
        self.auto_layout_button.clicked.connect(self._auto_layout)
        bottom.addWidget(self.auto_layout_button)
        self.wrap_text = QCheckBox('Bryt tekst')
        self.wrap_text.setToolTip('Felles innstilling for tekstbryting i resultatvisninger. Gjelder også nye vinduer.')
        self.wrap_text.setChecked(word_wrap_enabled())
        self.wrap_text.toggled.connect(self._set_wrap_text)
        bottom.addWidget(self.wrap_text)
        self.sort_reset = QPushButton('Nullstill sortering')
        self.sort_reset.clicked.connect(self._reset_sorting)
        bottom.addWidget(self.sort_reset)
        self.mode = QComboBox(self)
        self.mode.addItem('Lesbar XML', True)
        self.mode.addItem('Serialisert XML', False)
        self.mode.setToolTip('Serialisert XML er ikke byteidentisk med originalfilen.')
        self.mode.currentIndexChanged.connect(self._switch_xml_mode)
        bottom.addWidget(self.mode)
        self.export_button = QPushButton('Eksporter XML…')
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._export_xml)
        bottom.addWidget(self.export_button)
        close = QPushButton('Lukk')
        close.clicked.connect(self.close)
        bottom.addWidget(close)
        outer.addLayout(bottom)

    def _search(self):
        from PySide6.QtCore import QTimer
        if self._pending is not None or self._context_pending is not None:
            return
        expected_xpath = source_xpath_for_finding(self.finding.test_id, self.finding.field)
        if not expected_xpath:
            self.message.setText('Ingen dokumentert kildefelt-mapping for denne kontrollen.')
            return
        value = str(self.values.currentData())
        self.search_button.setEnabled(False)
        self.message.setText('Leser XML skrivebeskyttet – inntil 25 treff ...')
        self._pending = self._pool.submit(find_xml_values, self.xml_path, expected_xpath, value)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(100)

    def _poll(self):
        if not self._pending or not self._pending.done():
            return
        self._timer.stop()
        future, self._pending = self._pending, None
        self.search_button.setEnabled(True)
        try:
            self.rows = future.result()
        except (OSError, ValueError, RuntimeError) as exc:
            self.message.setText('Kunne ikke lese XML: ' + str(exc))
            return
        self.results.setSortingEnabled(False)
        self._selected_xpath = None
        self._selected_context = None
        self.export_button.setEnabled(False)
        self.results.setRowCount(len(self.rows))
        for index, result in enumerate(self.rows):
            # Qt.UserRole preserves source identity when the table is sorted.
            for col, value in enumerate((result.line, result.xpath, result.system_id or '', result.value)):
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.DisplayRole, int(value) if col == 0 else str(value))
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.results.setItem(index, col, item)
        self.results.setSortingEnabled(False)
        self._sort_column = None
        self._sort_direction = None
        self.results.horizontalHeader().setSortIndicatorShown(False)
        self.results.resizeColumnsToContents()
        self.results.setColumnWidth(1, max(self.results.columnWidth(1), 650))
        self.results.setColumnWidth(2, min(max(self.results.columnWidth(2), 320), 440))
        self.message.setText(f'{len(self.rows)} konkrete treff funnet. '
                             + ('Visningen er begrenset til de første 25; dette er ikke en ny totalopptelling.'
                                if len(self.rows) == 25 else 'Ingen andre treff i undersøkt kildefil.'))
        if self.rows:
            self.results.selectRow(0)
        QTimer.singleShot(0, self._auto_layout)

    def _set_wrap_text(self, enabled):
        save_word_wrap_enabled(enabled)
        apply_word_wrap(enabled, self.results, self.structure, self.xml_text)
        # XML is rewrapped by Qt in its viewport; the underlying source is unchanged.
        self.results.viewport().update()
        self.structure.viewport().update()

    def _auto_layout(self):
        """Fit a readable, restrained window; never maximize to a widescreen."""
        screen = QGuiApplication.screenAt(self.frameGeometry().center()) or self.screen()
        if screen is not None:
            area = screen.availableGeometry()
            target_width = min(area.width(), 1500, max(850, int(area.width() * .76)))
            target_height = min(area.height(), 980, max(620, int(area.height() * .90)))
            self.resize(target_width, target_height)
            # Clamp the *whole window*, not merely its center, to this monitor.
            frame = self.frameGeometry()
            self.move(max(area.left(), min(frame.left(), area.right() - frame.width() + 1)),
                      max(area.top(), min(frame.top(), area.bottom() - frame.height() + 1)))
        # Let Qt finish resize/layout before computing actual viewport widths.
        QTimer.singleShot(0, self._fit_panes)

    def _fit_panes(self):
        """Apply once on request/search; later manual splitter choices are retained."""
        available_height = max(1, self.vertical_splitter.height())
        self.vertical_splitter.setSizes([int(available_height * .36),
                                         int(available_height * .64)])
        available_width = max(1, self.lower_splitter.width())
        self.lower_splitter.setSizes([int(available_width * .49),
                                      int(available_width * .51)])
        QTimer.singleShot(0, self._fit_columns)

    def _fit_columns(self):
        # Use actual viewport width to avoid hiding the right-hand tree column.
        table_width = max(1, self.results.viewport().width() - 8)
        self.results.setColumnWidth(0, 56)
        remaining = max(240, table_width - 56)
        self.results.setColumnWidth(1, int(remaining * .56))
        self.results.setColumnWidth(2, int(remaining * .27))
        self.results.setColumnWidth(3, max(80, remaining - int(remaining * .56) - int(remaining * .27)))
        tree_width = max(1, self.structure.viewport().width() - 8)
        tree_first = max(130, int(tree_width * .40))
        tree_first = min(tree_first, max(80, tree_width - 120))
        self.structure.setColumnWidth(0, tree_first)
        self.structure.setColumnWidth(1, max(80, tree_width - tree_first))

    def _selection_changed(self):
        from PySide6.QtCore import QTimer
        cell = self.results.item(self.results.currentRow(), 0)
        index = cell.data(Qt.ItemDataRole.UserRole) if cell is not None else None
        if not isinstance(index, int) or not 0 <= index < len(self.rows):
            return
        occurrence = self.rows[index]
        if self._selected_xpath == occurrence.xpath:
            return
        self._selected_xpath = occurrence.xpath
        self._selected_context = None
        self.export_button.setEnabled(False)
        self.structure.clear()
        self.xml_text.setPlainText('Valgt XML-felt (kildeutdrag):\n' + occurrence.xml
                                   + '\n\nLeser omkringliggende XML-seksjon ...')
        self.context_status.setText('Undersøker kontekst for linje ' + str(occurrence.line))
        # Context requests are serial to avoid concurrent full-file scans.
        # If a previous request is running, queue the latest selection.
        if self._context_pending is None:
            self._launch_context(occurrence.xpath)

    def _launch_context(self, xpath):
        from PySide6.QtCore import QTimer
        self._context_pending_xpath = xpath
        self._context_pending = self._pool.submit(inspect_xml_context, self.xml_path, xpath)
        self._context_timer = QTimer(self)
        self._context_timer.timeout.connect(self._poll_context)
        self._context_timer.start(100)

    def _poll_context(self):
        if self._context_pending is None or not self._context_pending.done():
            return
        self._context_timer.stop()
        completed = self._context_pending
        requested_xpath = self._context_pending_xpath
        self._context_pending = None
        self._context_pending_xpath = None
        try:
            context = completed.result()
        except (OSError, ValueError, RuntimeError) as exc:
            context = None
            message = str(exc)
        # Selection may have moved while the worker was running.
        if context is None:
            if self._selected_xpath and self._selected_xpath != requested_xpath:
                self._launch_context(self._selected_xpath)
            else:
                self.context_status.setText('Kontekst ikke tilgjengelig: ' + message)
            return  # Do not retry the same failed source read forever.
        if context.xpath == self._selected_xpath:
            self._display_context(context)
        elif self._selected_xpath:
            self._launch_context(self._selected_xpath)

    def _display_context(self, context):
        self.structure.clear()
        parent = None
        for level in context.levels:
            ordinal = (f'{level.position} av {level.total}' if level.total is not None
                       else f'nr. {level.position} (totalt antall ikke undersøkt)')
            label = f'{level.element} – {ordinal}'
            info = ' · '.join(v for v in (level.system_id, level.title) if v)
            node = QTreeWidgetItem([label, info]) if parent is None else QTreeWidgetItem(parent, [label, info])
            if parent is None:
                self.structure.addTopLevelItem(node)
            if level.selected:
                node.setSelected(True)
            node.setExpanded(True)
            parent = node
        self._selected_context = context
        self.export_button.setEnabled(True)
        self._render_xml()
        self.context_status.setText('Kontekst: ' + context.scope
                                    + (' – utdrag avkortet, original uendret' if context.truncated else ' – full valgt seksjon'))

    def _render_xml(self):
        context = self._selected_context
        if context is None:
            return
        xml = context.xml
        if self._readable_mode and not context.truncated:
            try:
                xml = readable_xml(xml)
            except ValueError:
                pass
        self.xml_text.setPlainText(
            f'Kilde: {context.source}\nLinje: {context.line}\nXPath: {context.xpath}\n'
            f'XML-seksjon: {context.scope}\n\n' + xml)

    def _switch_xml_mode(self, _index):
        self._readable_mode = bool(self.mode.currentData())
        self._render_xml()

    def _click_sort(self, column):
        if self._sort_column != column:
            self._sort_column = column
            self._sort_direction = Qt.SortOrder.AscendingOrder
        elif self._sort_direction == Qt.SortOrder.AscendingOrder:
            self._sort_direction = Qt.SortOrder.DescendingOrder
        else:
            self._reset_sorting()
            return
        self.results.sortItems(column, self._sort_direction)
        self.results.horizontalHeader().setSortIndicator(column, self._sort_direction)
        self.results.horizontalHeader().setSortIndicatorShown(True)

    def _reset_sorting(self):
        if not self.rows:
            return
        cell = self.results.item(self.results.currentRow(), 0)
        selected_index = cell.data(Qt.ItemDataRole.UserRole) if cell else None
        self.results.setSortingEnabled(False)
        self.results.blockSignals(True)
        for row in range(len(self.rows)):
            current = next((r for r in range(row, len(self.rows))
                            if self.results.item(r, 0) is not None
                            and self.results.item(r, 0).data(Qt.ItemDataRole.UserRole) == row), None)
            if current is not None and current != row:
                # QTableWidget has no moveRow; reassign all items across rows.
                first = [self.results.takeItem(row, c) for c in range(4)]
                second = [self.results.takeItem(current, c) for c in range(4)]
                for c in range(4):
                    self.results.setItem(row, c, second[c])
                    self.results.setItem(current, c, first[c])
        self.results.blockSignals(False)
        self.results.horizontalHeader().setSortIndicatorShown(False)
        self._sort_column = None
        self._sort_direction = None
        if isinstance(selected_index, int):
            self.results.selectRow(selected_index)
        self.results.setSortingEnabled(False)

    def _export_xml(self):
        context = self._selected_context
        if context is None or context.xpath != self._selected_xpath:
            QMessageBox.warning(self, 'XML-eksport', 'Velg en ferdig undersøkt forekomst først.')
            return
        work = work_from_report(self.finding.report_path)
        if work is None:
            QMessageBox.warning(self, 'XML-eksport', 'Fant ikke jobbens Work. Eksport er ikke utført.')
            return
        selected = next((r for r in self.rows if r.xpath == self._selected_xpath), None)
        choices = ('Hele kontekstseksjonen', 'Valgt metadatafelt')
        from PySide6.QtWidgets import QInputDialog
        option, ok = QInputDialog.getItem(self, 'Eksporter XML', 'Velg XML-utdrag:', choices, 0, False)
        if not ok:
            return
        whole = option == choices[0]
        if whole and context.truncated:
            QMessageBox.warning(self, 'XML-eksport', 'Konteksten er avkortet; velg et mindre utdrag.')
            return
        if not whole and selected is None:
            return
        try:
            folder = save_xml_extract(
                work, source=self.xml_path, xpath=context.xpath,
                xml_text=context.xml if whole else selected.xml,
                scope=context.scope if whole else 'metadatafelt',
                line=context.line if whole else selected.line,
                test_id=self.finding.test_id, full_section=whole)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'XML-eksport', str(exc))
            return
        QMessageBox.information(self, 'XML-eksport',
                                f'XML-utdrag og manifest lagret i jobbens Work:\n{folder}')

    def closeEvent(self, event):
        if self._timer is not None:
            self._timer.stop()
        if self._context_timer is not None:
            self._context_timer.stop()
        self._pool.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)


def install_standard_values_link(viewer):
    """Add direct navigation to genuine findings in selected stored reports."""
    if getattr(viewer, '_a14_a2_std_installed', False):
        return
    viewer._a14_a2_std_installed = True
    page = viewer._pages['Oversikt']
    row = QHBoxLayout()
    status = QLabel()
    status.setWordWrap(True)
    row.addWidget(status, 1)
    button = QPushButton('Vis standardverdikontroller…')
    row.addWidget(button)
    # Reuse the existing PRONOM/action row when present. Do not consume a
    # second full-height row above the result table on small screens.
    existing = page.layout().itemAt(0)
    if existing is not None and isinstance(existing.layout(), QHBoxLayout):
        existing.layout().insertWidget(1, button)
        status.hide()
    else:
        page.layout().insertLayout(0, row)

    def update_label():
        findings = findings_from_snapshots(getattr(viewer, '_snapshots', ()))
        count = len(findings)
        status.setText(f'Standardverdier: {count} kontroller har ekstra observerte verdier.'
                       if count else 'Standardverdier: Ingen ekstra observerte verdier dokumentert.')
        button.setText(f'Standardverdier ({count})…')
        button.setToolTip(status.text())
        button.setEnabled(bool(count))
        return findings

    def open_details():
        findings = update_label()
        if not findings:
            return
        dialog = StandardValuesDialog(viewer, findings)
        # Parent the dialog to Resultatvisninger so it stays on the same monitor.
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.exec()

    button.clicked.connect(open_details)
    original_refresh = viewer.refresh
    def refreshed(*args, **kwargs):
        outcome = original_refresh(*args, **kwargs)
        update_label()
        return outcome
    viewer.refresh = refreshed
    update_label()
