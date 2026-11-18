"""Interactive KS workshop over the existing a3/a13 assessment and export APIs.

Instantiated only on explicit user action; the desktop's conservative Qt
startup path never imports this module or adds global event filters.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTabWidget,
    QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
    QInputDialog,
)

from app.ks_workshop_v022_a12 import (
    SECTIONS, RECOMMENDATIONS, WorkshopError, actor_from_profile,
    build_workspace, export_report, filter_findings, findings_with_reviews,
    render_preview, save_observation, save_review, source_catalog,
    technical_tests, work_file,
)
from noark5_workflow.reporting.qa_review_v021_a13 import STATUSES


def _part_id(part: dict) -> str:
    return str(part.get('system_id') or part.get('id') or '')


def _part_context(part: dict) -> str:
    return 'Arkivdel: ' + str(part.get('title') or '(uten navn)') + ' [' + _part_id(part) + ']'


class KsWorkshopDialog(QDialog):
    """One selected job's source-bound KS view; never read another Work implicitly."""

    def __init__(self, work: str | Path, parent=None):
        super().__init__(parent)
        self.work = Path(work).resolve(strict=True)
        self.snapshot = None
        self.all_findings = ()
        self.tests = ()
        self.sources = ()
        self._selected_key = ''
        self._loading = False
        self._unsaved = False
        self._report_path = None
        self._recommendation_saved = False
        self.setWindowTitle('Kvalitetssikring og godkjenningsrapport – UTKAST')
        self.setMinimumSize(810, 565)
        screen = (parent.screen() if parent is not None else QApplication.primaryScreen())
        size = screen.availableGeometry() if screen else None
        self.resize(min(1350, max(820, size.width() - 90)) if size else 1200,
                    min(875, max(590, size.height() - 90)) if size else 790)
        self._build_ui()
        self._reload()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        self.heading = QLabel('Kvalitetssikring – kildebundet uttrekk')
        self.heading.setWordWrap(True)
        outer.addWidget(self.heading)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        outer.addWidget(self.summary)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        self._build_findings_tab()
        self._build_tests_tab()
        self._build_parts_tab()
        self._build_sources_tab()
        self._build_report_tab()
        actions = QHBoxLayout()
        refresh = QPushButton('Oppdater fra Work')
        refresh.clicked.connect(self._request_reload)
        actions.addWidget(refresh)
        actions.addStretch(1)
        close = QPushButton('Lukk KS-arbeidsflate')
        close.clicked.connect(self._request_close)
        actions.addWidget(close)
        outer.addLayout(actions)

    @staticmethod
    def _tree(headers: list[str]) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setHeaderLabels(headers)
        tree.setAlternatingRowColors(True)
        tree.setRootIsDecorated(False)
        tree.setUniformRowHeights(True)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        tree.header().setStretchLastSection(False)
        for idx in range(len(headers)):
            tree.header().setSectionResizeMode(idx, QHeaderView.ResizeMode.Interactive)
        return tree

    def _build_findings_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        filterrow = QHBoxLayout()
        self.filter_source = QComboBox()
        self.filter_source.addItem('Alle kontrollkilder', '')
        self.filter_severity = QComboBox()
        for label, value in (('Alle nivåer', ''), ('FEIL', 'ERROR'),
                             ('Advarsler', 'WARNING'), ('Vurdering', 'REVIEW'),
                             ('Merknader', 'NOTE'), ('Informasjon', 'INFORMATION')):
            self.filter_severity.addItem(label, value)
        self.filter_review = QComboBox()
        for label, value in (('Alle vurderinger', ''), ('Ikke vurdert', 'pending'),
                             ('Faglig vurdert', 'reviewed')):
            self.filter_review.addItem(label, value)
        self.filter_search = QLineEdit()
        self.filter_search.setPlaceholderText('Søk i test-ID, melding, arkivdel eller kommentar…')
        for widget in (self.filter_source, self.filter_severity, self.filter_review):
            filterrow.addWidget(widget)
            widget.currentIndexChanged.connect(self._refresh_findings_table)
        filterrow.addWidget(self.filter_search, 1)
        self.filter_search.textChanged.connect(self._refresh_findings_table)
        layout.addLayout(filterrow)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        self.findings_tree = self._tree(['Test-ID', 'Kilde', 'Nivå', 'Funn / kontekst', 'KS-status'])
        self.findings_tree.setColumnWidth(0, 125)
        self.findings_tree.setColumnWidth(1, 185)
        self.findings_tree.setColumnWidth(2, 80)
        self.findings_tree.setColumnWidth(3, 580)
        self.findings_tree.setColumnWidth(4, 140)
        self.findings_tree.currentItemChanged.connect(self._finding_selected)
        splitter.addWidget(self.findings_tree)
        detail = QWidget()
        d = QVBoxLayout(detail)
        self.finding_detail = QTextBrowser()
        self.finding_detail.setOpenExternalLinks(False)
        self.finding_detail.setMaximumHeight(125)
        d.addWidget(self.finding_detail)
        row = QHBoxLayout()
        row.addWidget(QLabel('Faglig status:'))
        self.review_status = QComboBox()
        self.review_status.addItem('Ikke vurdert', '')
        for code, label in STATUSES.items():
            self.review_status.addItem(label, code)
        row.addWidget(self.review_status, 1)
        self.include_ks = QCheckBox('Ta med kommentar i KS-rapport')
        self.include_ks.setChecked(True)
        row.addWidget(self.include_ks)
        self.include_depot = QCheckBox('Ta med i depotrapport')
        self.include_depot.setChecked(True)
        row.addWidget(self.include_depot)
        d.addLayout(row)
        self.review_comment = QPlainTextEdit()
        self.review_comment.setPlaceholderText('Faglig forklaring, uavklarte forhold, svar, begrunnelse eller oppfølging…')
        self.review_comment.setMaximumHeight(125)
        d.addWidget(self.review_comment)
        self.review_save = QPushButton('Lagre faglig vurdering')
        self.review_save.clicked.connect(self._save_finding)
        obs = QPushButton('Registrer ny observasjon…')
        obs.clicked.connect(lambda: self._new_observation('Hele uttrekket'))
        buttons = QHBoxLayout()
        buttons.addWidget(self.review_save)
        buttons.addWidget(obs)
        buttons.addStretch(1)
        d.addLayout(buttons)
        splitter.addWidget(detail)
        splitter.setSizes([340, 310])
        layout.addWidget(splitter, 1)
        self.tabs.addTab(page, 'Funn og vurderinger')
        for w in (self.review_status, self.include_ks, self.include_depot):
            w.currentIndexChanged.connect(self._mark_unsaved) if isinstance(w, QComboBox) else w.toggled.connect(self._mark_unsaved)
        self.review_comment.textChanged.connect(self._mark_unsaved)

    def _build_tests_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel('Samtlige tilgjengelige DWM XPath- og Arkade Noark-testresultater, med XSD og PRONOM-kilder. '
                      '«OK» betyr kontrollens tekniske status, ikke faglig godkjenning. '
                      'Dobbeltklikk for å åpne original evidensfil.')
        note.setWordWrap(True)
        layout.addWidget(note)
        top = QHBoxLayout()
        self.test_filter = QLineEdit()
        self.test_filter.setPlaceholderText('Søk i kontrollmotor, test-ID, navn og status…')
        self.test_filter.textChanged.connect(self._refresh_tests_table)
        self.test_engine = QComboBox()
        self.test_engine.addItem('Alle kontrollmotorer', '')
        self.test_engine.currentIndexChanged.connect(self._refresh_tests_table)
        top.addWidget(self.test_engine)
        self.test_status = QComboBox()
        for label, key in (('Alle teststatuser', ''), ('FEIL', 'feil'),
                           ('WARNING', 'warning'), ('OK', 'ok'), ('Rapportert', 'rapportert')):
            self.test_status.addItem(label, key)
        self.test_status.currentIndexChanged.connect(self._refresh_tests_table)
        top.addWidget(self.test_status)
        top.addWidget(self.test_filter, 1)
        layout.addLayout(top)
        self.tests_tree = self._tree(['Kontrollmotor', 'Test-ID', 'Navn', 'Status', 'Merknad / antall'])
        for n, width in enumerate([170, 110, 450, 105, 190]):
            self.tests_tree.setColumnWidth(n, width)
        self.tests_tree.itemDoubleClicked.connect(lambda item, _col: self._open_relative(item.data(0, Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.tests_tree, 1)
        self.tests_count = QLabel()
        layout.addWidget(self.tests_count)
        self.tabs.addTab(page, 'Alle tester')

    def _build_parts_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel('Arkivdeloversikt fra lagret DWM-depotrapport. Marker arkivdel og registrer en faglig merknad. '
                      'Den registreres som en manuell KS-observasjon, ikke som maskinfeil.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.parts_tree = self._tree(['Arkivdel', 'Status', 'Start', 'Slutt', 'System-ID'])
        for i, width in enumerate([370, 180, 115, 115, 250]):
            self.parts_tree.setColumnWidth(i, width)
        layout.addWidget(self.parts_tree, 1)
        button = QPushButton('Registrer merknad til valgt arkivdel…')
        button.clicked.connect(self._part_observation)
        layout.addWidget(button)
        self.tabs.addTab(page, 'Arkivdeler')

    def _build_sources_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel('Kildeoversikt fra KS-grunnlagets manifest. Filstier er bundet til valgt Work; '
                      'Original Source endres aldri. Dobbeltklikk på en fil for å åpne den.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.sources_tree = self._tree(['Kildetype', 'Fil i Work', 'SHA-256', 'Integritet'])
        for i, width in enumerate([170, 550, 260, 105]):
            self.sources_tree.setColumnWidth(i, width)
        self.sources_tree.itemDoubleClicked.connect(lambda item, _col: self._open_relative(item.data(0, Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.sources_tree, 1)
        open_button = QPushButton('Åpne valgt kildefil')
        open_button.clicked.connect(self._open_selected_source)
        layout.addWidget(open_button)
        self.tabs.addTab(page, 'Kilder og evidens')

    def _build_report_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel('Velg innhold i rapportens lesbare forside. Hele funnregisteret og original evidens '
                      'beholdes alltid i den etablerte KS-rapportpakken, selv om en seksjon ikke er valgt her.')
        note.setWordWrap(True)
        layout.addWidget(note)
        controls = QHBoxLayout()
        section_box = QGroupBox('Rapportseksjoner')
        section_layout = QVBoxLayout(section_box)
        self.section_checks = {}
        for key, label in SECTIONS:
            check = QCheckBox(label)
            check.setChecked(True)
            section_layout.addWidget(check)
            self.section_checks[key] = check
        controls.addWidget(section_box)
        recommendation_box = QGroupBox('Faglig innstilling (ikke vedtak)')
        form = QFormLayout(recommendation_box)
        self.recommendation = QComboBox()
        for key, label in RECOMMENDATIONS.items():
            self.recommendation.addItem(label, key)
        self.recommendation.currentIndexChanged.connect(self._recommendation_changed)
        form.addRow('Forslag:', self.recommendation)
        self.recommendation_note = QPlainTextEdit()
        self.recommendation_note.setPlaceholderText('Oppsummer avklaringer og hva som må være oppfylt før en beslutning…')
        self.recommendation_note.setMinimumHeight(100)
        self.recommendation_note.textChanged.connect(self._recommendation_changed)
        form.addRow('Begrunnelse:', self.recommendation_note)
        save_recommendation = QPushButton('Lagre innstilling i KS-register')
        save_recommendation.clicked.connect(self._save_recommendation)
        form.addRow(save_recommendation)
        controls.addWidget(recommendation_box, 1)
        layout.addLayout(controls)
        buttons = QHBoxLayout()
        preview = QPushButton('Forhåndsvis utkast')
        preview.clicked.connect(self._preview)
        buttons.addWidget(preview)
        export = QPushButton('Generer KS-/godkjenningsrapport…')
        export.clicked.connect(self._export)
        buttons.addWidget(export)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.preview_browser = QTextBrowser()
        self.preview_browser.setOpenExternalLinks(False)
        layout.addWidget(self.preview_browser, 1)
        self.tabs.addTab(page, 'Rapportutkast')

    def _request_close(self):
        if self._confirm_unsaved():
            self.accept()

    def closeEvent(self, event):
        if self._confirm_unsaved():
            event.accept()
        else:
            event.ignore()

    def _mark_unsaved(self, *_args):
        if not self._loading and self._selected_key:
            self._unsaved = True

    def _confirm_unsaved(self) -> bool:
        if not self._unsaved:
            return True
        answer = QMessageBox.question(self, 'Ulagret faglig vurdering',
                        'Du har endret vurderingen uten å lagre. Forkaste endringene?',
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def _request_reload(self):
        if self._confirm_unsaved():
            self._reload()

    def _reload(self, *, select_key: str = ''):
        try:
            self.snapshot = build_workspace(self.work)
            self.all_findings = findings_with_reviews(self.work, self.snapshot)
            self.tests = technical_tests(self.work, self.snapshot)
            self.sources = source_catalog(self.work, self.snapshot)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kan ikke lese KS-grunnlaget', str(exc))
            if self.snapshot is None:
                raise
            return
        ident = self.snapshot['work_identity']
        reviewed = sum(bool(row.get('review_status')) for row in self.all_findings)
        self.heading.setText(f"{ident.get('job_id', '')} – {ident.get('job_name', '')} · {self.work}")
        self.summary.setText(
            f"Funn: {len(self.all_findings)} · Faglig vurdert: {reviewed} · "
            f"Uavklart: {len(self.all_findings) - reviewed} · Teknisk testvisning: {len(self.tests)}. "
            "UTKAST – ingen automatisk godkjenning.")
        old_source = self.filter_source.currentData()
        self.filter_source.blockSignals(True)
        self.filter_source.clear()
        self.filter_source.addItem('Alle kontrollkilder', '')
        for source in sorted({str(row.get('source') or '') for row in self.all_findings} - {''}):
            self.filter_source.addItem(source, source)
        self.filter_source.setCurrentIndex(max(0, self.filter_source.findData(old_source)))
        self.filter_source.blockSignals(False)
        self._unsaved = False
        self._selected_key = ''
        self._refresh_findings_table(select_key=select_key)
        old_engine = self.test_engine.currentData()
        self.test_engine.blockSignals(True)
        self.test_engine.clear()
        self.test_engine.addItem('Alle kontrollmotorer', '')
        for engine in sorted({t['engine'] for t in self.tests}):
            self.test_engine.addItem(engine, engine)
        self.test_engine.setCurrentIndex(max(0, self.test_engine.findData(old_engine)))
        self.test_engine.blockSignals(False)
        self._refresh_tests_table()
        self._refresh_parts_table()
        self._refresh_sources_table()

    def _refresh_findings_table(self, *_args, select_key: str = ''):
        selected = select_key or self._selected_key
        if self._unsaved:
            if not self._confirm_unsaved():
                return
            self._unsaved = False
        rows = filter_findings(self.all_findings,
                               severity=self.filter_severity.currentData() or '',
                               source=self.filter_source.currentData() or '',
                               review=self.filter_review.currentData() or '',
                               search=self.filter_search.text())
        self.findings_tree.blockSignals(True)
        self.findings_tree.clear()
        for row in rows:
            status = STATUSES.get(row.get('review_status') or '', 'Ikke vurdert')
            item = QTreeWidgetItem([str(row.get('test_id') or ''), str(row.get('source') or ''),
                                    str(row.get('severity') or ''), str(row.get('message') or '')[:180], status])
            item.setData(0, Qt.ItemDataRole.UserRole, row['finding_key'])
            item.setToolTip(3, str(row.get('message') or '') + '\n' + str(row.get('context') or ''))
            self.findings_tree.addTopLevelItem(item)
            if row['finding_key'] == selected:
                self.findings_tree.setCurrentItem(item)
        if self.findings_tree.currentItem() is None and self.findings_tree.topLevelItemCount():
            self.findings_tree.setCurrentItem(self.findings_tree.topLevelItem(0))
        current = self.findings_tree.currentItem()
        self.findings_tree.blockSignals(False)
        self._finding_selected(current, None)

    def _finding_selected(self, current, _previous):
        key = str(current.data(0, Qt.ItemDataRole.UserRole) or '') if current else ''
        if key == self._selected_key:
            return
        if self._unsaved and not self._confirm_unsaved():
            for i in range(self.findings_tree.topLevelItemCount()):
                candidate = self.findings_tree.topLevelItem(i)
                if candidate.data(0, Qt.ItemDataRole.UserRole) == self._selected_key:
                    self.findings_tree.blockSignals(True)
                    self.findings_tree.setCurrentItem(candidate)
                    self.findings_tree.blockSignals(False)
                    return
        self._selected_key = key
        row = next((r for r in self.all_findings if r['finding_key'] == key), None)
        self._loading = True
        try:
            from html import escape
            if row is None:
                self.finding_detail.setPlainText('Velg et funn for faglig vurdering.')
            else:
                self.finding_detail.setHtml(
                    '<b>' + escape(str(row.get('source') or '')) + ' / '
                    + escape(str(row.get('test_id') or '')) + '</b><p>'
                    + escape(str(row.get('message') or '')) + '</p><p>'
                    + escape(str(row.get('context') or '')) + '</p><small>Work: '
                    + escape(str(row.get('source_ref') or '')) + '</small>')
            self.review_status.setCurrentIndex(max(0, self.review_status.findData(
                row.get('review_status') if row else '')))
            self.review_comment.setPlainText(str(row.get('review_comment') or '') if row else '')
            self.include_ks.setChecked(bool(row.get('include_in_ks', True)) if row else True)
            self.include_depot.setChecked(bool(row.get('include_in_depot', True)) if row else True)
            self.review_save.setEnabled(row is not None)
            self._unsaved = False
        finally:
            self._loading = False

    def _get_actor(self):
        from app.user_profile import load_user_profile
        profile = load_user_profile()
        if profile is None or not profile.is_complete:
            from gui_qt.depot_review_v019_a2 import ReviewUserProfileDialog
            dialog = ReviewUserProfileDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                raise WorkshopError('Opprett en brukerprofil før du lagrer faglig vurdering')
            profile = load_user_profile()
        return actor_from_profile(profile)

    def _save_finding(self):
        row = next((r for r in self.all_findings if r['finding_key'] == self._selected_key), None)
        if row is None:
            return
        try:
            user = self._get_actor()
            if not self.review_status.currentData():
                raise WorkshopError('Velg faglig vurderingsstatus før lagring')
            save_review(self.work, self.snapshot, row,
                        status=self.review_status.currentData(),
                        comment=self.review_comment.toPlainText(), user=user,
                        include_in_ks=self.include_ks.isChecked(),
                        include_in_depot=self.include_depot.isChecked())
            self._unsaved = False
            self._reload(select_key=self._selected_key)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kunne ikke lagre vurdering', str(exc))

    def _new_observation(self, context: str):
        if self._unsaved and not self._confirm_unsaved():
            return
        text, ok = QInputDialog.getMultiLineText(
            self, 'Ny faglig observasjon', 'Beskriv uklarhet, forklaring eller forhold til oppfølging:', '')
        if not ok or not text.strip():
            return
        level, ok = QInputDialog.getItem(self, 'Observasjonsnivå', 'Velg nivå:',
                                          ['REVIEW', 'WARNING', 'ERROR', 'NOTE', 'INFORMATION'], 0, False)
        if not ok:
            return
        try:
            save_observation(self.work, self.snapshot, severity=level,
                             message=text.strip(), context=context, user=self._get_actor())
            self._reload()
            self.tabs.setCurrentIndex(0)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kunne ikke lagre observasjon', str(exc))

    def _part_observation(self):
        item = self.parts_tree.currentItem()
        if item is None:
            QMessageBox.information(self, 'Arkivdel', 'Velg en arkivdel først.')
            return
        self._new_observation(str(item.data(0, Qt.ItemDataRole.UserRole)))

    def _refresh_tests_table(self, *_args):
        self.tests_tree.clear()
        query = self.test_filter.text().strip().casefold()
        visible = 0
        engine = self.test_engine.currentData() or ''
        status = self.test_status.currentData() or ''
        for row in self.tests:
            if engine and row['engine'] != engine:
                continue
            if status and str(row['status']).casefold() != status:
                continue
            if query and query not in ' '.join(str(v) for v in row.values()).casefold():
                continue
            item = QTreeWidgetItem([row['engine'], row['test_id'], row['name'],
                                    row['status'], row['note']])
            item.setData(0, Qt.ItemDataRole.UserRole, row['source_ref'])
            item.setToolTip(2, row['name'])
            self.tests_tree.addTopLevelItem(item)
            visible += 1
        self.tests_count.setText(f'Viser {visible} av {len(self.tests)} tekniske test-/kildeposter')

    def _refresh_parts_table(self):
        self.parts_tree.clear()
        for p in self.snapshot.get('archive_parts') or ():
            item = QTreeWidgetItem([
                str(p.get('title') or ''), str(p.get('status') or ''),
                str(p.get('period_start') or p.get('archive_period_start_date') or ''),
                str(p.get('period_end') or p.get('archive_period_end_date') or ''),
                _part_id(p)])
            item.setData(0, Qt.ItemDataRole.UserRole, _part_context(p))
            self.parts_tree.addTopLevelItem(item)

    def _refresh_sources_table(self):
        self.sources_tree.clear()
        for row in self.sources:
            item = QTreeWidgetItem([str(row['type']), str(row['path']),
                                    str(row['sha256'])[:20], str(row.get('integrity') or 'Ukjent')])
            item.setData(0, Qt.ItemDataRole.UserRole, row['path'])
            item.setToolTip(1, str(row['path']))
            self.sources_tree.addTopLevelItem(item)

    def _open_selected_source(self):
        item = self.sources_tree.currentItem()
        if item is not None:
            self._open_relative(item.data(0, Qt.ItemDataRole.UserRole))

    def _open_relative(self, relative):
        try:
            path = work_file(self.work, str(relative or ''))
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except (OSError, WorkshopError) as exc:
            QMessageBox.warning(self, 'Kilden er ikke tilgjengelig', str(exc))

    def _report_sections(self):
        return tuple(k for k, w in self.section_checks.items() if w.isChecked())

    def _recommendation_changed(self, *_args):
        self._recommendation_saved = False

    def _preview(self):
        if self._unsaved:
            QMessageBox.warning(self, "Ulagret vurdering",
                                "Lagre eller forkast vurderingen av valgt funn først.")
            return
        try:
            text = render_preview(self.snapshot, self.all_findings, self.tests,
                                  self.sources, sections=self._report_sections(),
                                  recommendation=self.recommendation.currentData(),
                                  recommendation_note=self.recommendation_note.toPlainText())
            self.preview_browser.setHtml(text)
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kan ikke forhåndsvise', str(exc))

    def _save_recommendation(self):
        selected = self.recommendation.currentData()
        explanation = self.recommendation_note.toPlainText().strip()
        if selected == 'pending' or not explanation:
            QMessageBox.information(self, 'Faglig innstilling',
                                    'Velg et forslag og skriv en begrunnelse først.')
            return
        # No formal decision state is written: this is a manual QA observation
        # already understood by the existing a3/a13 audit and export.
        try:
            save_observation(self.work, self.snapshot, severity='REVIEW',
                             message='Foreløpig KS-innstilling: ' + RECOMMENDATIONS[selected]
                                     + '\nBegrunnelse: ' + explanation,
                             context='Hele uttrekket – beslutningsutkast, ikke formell godkjenning',
                             user=self._get_actor())
            self._reload()
            self._recommendation_saved = True
            QMessageBox.information(self, 'Innstilling lagret',
                                    'Innstillingen er registrert som faglig observasjon i Work.')
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kunne ikke lagre innstilling', str(exc))

    def _export(self):
        if self._unsaved:
            QMessageBox.warning(self, 'Ulagret vurdering',
                                'Lagre eller forkast endringen i valgt funn før rapporteksport.')
            return
        if self.recommendation.currentData() != "pending" and not self._recommendation_saved:
            QMessageBox.warning(self, "Innstillingen er ikke lagret",
                                "Lagre den faglige innstillingen i KS-registeret før eksport. "
                                "Da blir den med i den revisjonssikre vurderingshistorikken.")
            return
        folder = QFileDialog.getExistingDirectory(self, 'Velg overordnet mappe for rapportpakken',
                                                   str(Path.home()))
        if not folder:
            return
        ident = self.snapshot['work_identity']
        safe_id = ''.join(c if c.isalnum() or c in '-_' else '_' for c in str(ident.get('job_id') or 'JOB'))
        target = Path(folder) / ('KS_' + safe_id + '_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
        if target.exists():
            QMessageBox.warning(self, 'Eksport', 'Rapportmappen finnes allerede. Velg nytt tidspunkt.')
            return
        reply = QMessageBox.question(self, 'Generer KS-/godkjenningsrapport',
            'DWM eksporterer en UTKAST-rapport med hele avviksregisteret, valgte '
            'presentasjonsseksjoner og kildereferanser. Ingen formell godkjenning registreres.\n\n'
            + str(target), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            output = export_report(self.work, target, sections=self._report_sections(),
                                   recommendation=self.recommendation.currentData(),
                                   recommendation_note=self.recommendation_note.toPlainText())
            self._report_path = output['workshop_html']
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._report_path)))
            QMessageBox.information(self, 'Rapportutkast generert',
                'Komplett rapportpakke og forhåndsvisning er lagret i:\n' + str(output['directory'])
                + '\n\nDette er ikke et formelt godkjenningsvedtak.')
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kunne ikke generere rapportpakke', str(exc))
