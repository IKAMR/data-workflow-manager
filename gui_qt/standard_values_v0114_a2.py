"""Standard-value drilldown from Resultatvisninger / Oversikt.

Only saved depot-report evidence is displayed. Source XML is never opened or
modified, and no XPath/system ID is invented when the report lacks it.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QFileDialog, QComboBox, QPlainTextEdit,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
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
        for row, finding in enumerate(self._findings):
            reference = reference_for_finding(finding.test_id, finding.field, finding.version)
            metadata_id = reference['metadata_id'] if reference else '–'
            cells = (extract_display_name(finding.job_name, finding.report_path), metadata_id, finding.test_id, finding.field,
                     finding.version or '–', str(finding.extra_total),
                     'Undersøk kilde')
            for col, cell in enumerate(cells):
                cell_item = QTableWidgetItem(cell)
                if col == 0:
                    cell_item.setToolTip(f'Jobbnavn: {finding.job_name}\nRapport: {finding.report_path or "Ikke oppgitt"}')
                self.table.setItem(row, col, cell_item)
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
        index = self.table.currentRow()
        return self._findings[index] if 0 <= index < len(self._findings) else None

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
    """Bounded, read-only XML search for one observed value."""

    def __init__(self, parent, xml_path, finding):
        super().__init__(parent)
        self.setWindowTitle('XML-evidens – ' + finding.test_id)
        self.resize(1020, 650)
        self.xml_path = Path(xml_path)
        self.finding = finding
        self.rows = ()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='dwm-xml-source')
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
        self.message = QLabel('Velg Finn forekomster for å undersøke original XML. Maks 25 treff.')
        self.message.setWordWrap(True)
        outer.addWidget(self.message)
        self.results = QTableWidget(0, 4, self)
        self.results.setHorizontalHeaderLabels(('Linje', 'XML-sti (XPath)', 'System-ID', 'Verdi'))
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results.setColumnWidth(0, 75)
        self.results.setColumnWidth(1, 540)
        self.results.setColumnWidth(2, 170)
        outer.addWidget(self.results, 3)
        self.xml_text = QPlainTextEdit(self)
        self.xml_text.setReadOnly(True)
        self.xml_text.setPlaceholderText('Velg en forekomst for å se et faktisk XML-utdrag.')
        outer.addWidget(self.xml_text, 2)
        self.results.itemSelectionChanged.connect(self._selection_changed)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = QPushButton('Lukk')
        close.clicked.connect(self.close)
        bottom.addWidget(close)
        outer.addLayout(bottom)
        self._pending = None
        self._timer = None

    def _search(self):
        from PySide6.QtCore import QTimer
        if self._pending is not None:
            return
        field = self.finding.field
        expected_xpath = source_xpath_for_finding(self.finding.test_id, field)
        if not expected_xpath:
            self.message.setText('Ingen kildefelt-mapping dokumentert for denne kontrollen.')
            return
        value = str(self.values.currentData())
        self.search_button.setEnabled(False)
        self.message.setText('Leser XML skrivebeskyttet – første 25 treff ...')
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
        self.results.setRowCount(len(self.rows))
        for index, row in enumerate(self.rows):
            for col, value in enumerate((row.line, row.xpath, row.system_id or 'Ikke dokumentert', row.value)):
                self.results.setItem(index, col, QTableWidgetItem(str(value)))
        self.message.setText(
            f'{len(self.rows)} konkrete treff funnet. ' +
            ('Visningen er begrenset til de første 25; dette er ikke en ny totalopptelling.'
             if len(self.rows) == 25 else 'Ingen andre treff i den undersøkte XML-filen.'))
        if self.rows:
            self.results.selectRow(0)

    def _selection_changed(self):
        index = self.results.currentRow()
        if 0 <= index < len(self.rows):
            row = self.rows[index]
            self.xml_text.setPlainText('Fil: ' + str(self.xml_path) + '\n'
                                       'Linje: ' + str(row.line) + '\nXPath: ' + row.xpath + '\n\n'
                                       + row.xml)

    def closeEvent(self, event):
        # Worker may still be reading when user closes. It owns only a read-only
        # file descriptor and never touches Qt widgets.
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
