"""v0.1.10-a4/a5: read-only PRONOM comparisons and contextual actions.

The raw Arkade/RAF observation and the selected institutional PUID policy are
independent. a5 adds unmistakable source/date presentation and dated export.
No original evidence, source files, reports, or AIP content are modified.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSizePolicy,
)

from app.format_policy_v0110_a4 import (
    FORMAT_PROFILE_DIR, STATUS_ACCEPTED, STATUS_CLARIFY,
    STATUS_UNIDENTIFIED, STATUS_NOT_ASSESSED, STATUS_LABELS,
    discover_format_policies, evaluate_puid,
    load_format_policy, summarize_format_assessments,
)
from app.format_context_v0110_a5 import (
    comparison_labels, export_comparison_csv, read_pronom_import_context,
)
from app.result_display_v0110_a5 import (
    arkade_tests_from_depot, load_technical_test_names, technical_test_name,
)
from .result_detail_view_v0110_a5 import ResultDetailModesMixin
from .result_center_v018_a13 import DETAIL_ROLE, PATH_ROLE
from .result_center_v019_a1 import ResultCenterWindow as _PreviousResultCenter

_ORIGINAL_DETAIL_ROLE = Qt.ItemDataRole.UserRole + 51
_FORMAT_STATUS_ROLE = Qt.ItemDataRole.UserRole + 52

# Action placement changes presentation only; original buttons and callbacks are retained.
_CONTEXT_ACTIONS = {
    'Oversikt': ('Klassisk uttrekksoversikt…',),
    'Arkivdeler': ('Åpne kildefil',),
    'Tekniske kontroller': ('Åpne kildefil',),
    'Arkade 5': ('Åpne kildefil',),
    'PRONOM': ('Åpne kildefil',),
    'KDRS Query': ('Åpne kildefil', 'Velg KDRS-evidens…'),
    'Periodevurdering': ('Vurder periode…',),
    'Depotrapporter': ('Åpne kildefil', 'Lag rapport / samlerapport…'),
    'Evidensfiler': ('Åpne kildefil',),
    'Kildeoversikt': ('Åpne kildefil',),
    'Arkade-dekning': ('Åpne kildefil',),
}
_COMMON_ACTIONS = ('Oppdater visning', 'Åpne Work-mappe')


class ResultCenterWindow(ResultDetailModesMixin, _PreviousResultCenter):
    """Compare PUIDs against a selected dated policy without rewriting evidence."""

    def __init__(self, *args, **kwargs):
        self._a4_ready = False
        self._a4_settings = QSettings('IKAMR', 'DWM-Qt')
        self._a4_format_rows = []
        self._a4_format_policy = None
        self._a5_missing_policy_warning = ''
        super().__init__(*args, **kwargs)
        self._a53_install_details()
        self._a4_make_policy_controls()
        self._a4_make_context_actions()
        self._a5_make_discovery_link()
        self._a4_ready = True
        self._a4_select_initial_policy()
        self._a4_apply_context_actions()
        self._a53_enrich_result_tables()
        self._a56_configure_columns()
        self._a4_assess_pronom()
        self._a5_select_first_result()
        self._a53_schedule_splitter()

    def _a5_make_discovery_link(self):
        """Make the comparison easy to find even when the PRONOM tab is off-screen."""
        overview = self._pages['Oversikt']
        header = QHBoxLayout()
        hint = QLabel('Filformater: historisk Arkade/RAF og valgt regelprofil vises separat i PRONOM.')
        hint.setWordWrap(True)
        header.addWidget(hint, 1)
        button = QPushButton('Vis filformatvurderinger (PRONOM)')
        button.setToolTip('Åpne oversikt over kildeklassifisering og datert regelprofil.')
        button.clicked.connect(lambda: self.tabs.setCurrentWidget(self._pages['PRONOM']))
        header.addWidget(button)
        overview.layout().insertLayout(0, header)
        index = self.tabs.indexOf(self._pages['PRONOM'])
        if index >= 0:
            self.tabs.setTabToolTip(index, 'Arkade 5 / RAF-220301 mot valgt, datert formatregelprofil')

    def _a4_make_policy_controls(self):
        page = self._pages['PRONOM']
        layout = page.layout()
        intro = QLabel('TO UAVHENGIGE VURDERINGER   A: Arkade 5 / RAF-220301 (historisk)    '
                       'B: PUID mot valgt regelprofil (nå)')
        intro.setWordWrap(True)
        intro.setStyleSheet('font-weight: 600;')
        layout.insertWidget(0, intro)

        first = QHBoxLayout()
        first.addWidget(QLabel('Formatregler:'))
        self.format_policy_combo = QComboBox()
        self.format_policy_combo.setMinimumWidth(260)
        self.format_policy_combo.setToolTip(
            'Regelprofilen vurderer PUID-er, uten å endre Arkade- eller Siegfried-evidens.'
        )
        self.format_policy_combo.addItem('Ingen formatvurdering', '')
        self._a4_profiles = discover_format_policies()
        for policy in self._a4_profiles:
            self.format_policy_combo.addItem(policy.label, str(policy.path))
        first.addWidget(self.format_policy_combo, 1)
        browse = QPushButton('Last inn JSON-profil…')
        browse.setToolTip('Velg et lokalt, versjonert regelsett; filen må være JSON i DWM-format.')
        browse.clicked.connect(self._a4_browse_policy)
        first.addWidget(browse)
        layout.insertLayout(1, first)

        controls = QHBoxLayout()
        controls.addWidget(QLabel('Vurdering:'))
        self.format_status_combo = QComboBox()
        self.format_status_combo.addItem('Alle vurderinger', '')
        for status in (STATUS_ACCEPTED, STATUS_CLARIFY, STATUS_UNIDENTIFIED, STATUS_NOT_ASSESSED):
            self.format_status_combo.addItem(STATUS_LABELS[status], status)
        controls.addWidget(self.format_status_combo)
        controls.addWidget(QLabel('Søk:'))
        self.format_search = QLineEdit()
        self.format_search.setPlaceholderText('Uttrekk, PUID, filtype, versjon eller vurdering')
        controls.addWidget(self.format_search, 1)
        export = QPushButton('Eksporter vurdering til CSV…')
        export.setToolTip('Eksporter viste formatgrupper med begge kilder, import-/kopidato og SHA-256.')
        export.clicked.connect(self._a4_export_pronom)
        controls.addWidget(export)
        layout.insertLayout(2, controls)

        self.format_summary = QLabel()
        self.format_summary.setWordWrap(True)
        layout.insertWidget(3, self.format_summary)

        self.format_arkade_source = QLabel()
        self.format_arkade_source.setWordWrap(True)
        layout.insertWidget(4, self.format_arkade_source)
        provenance_row = QHBoxLayout()
        self.format_profile_source = QLabel()
        self.format_profile_source.setWordWrap(True)
        provenance_row.addWidget(self.format_profile_source, 1)
        more = QPushButton('Kilder og datoer…')
        more.setToolTip('Vis både historisk importproveniens og valgt formatprofils kildedata.')
        more.clicked.connect(self._a5_show_sources)
        provenance_row.addWidget(more)
        layout.insertLayout(5, provenance_row)

        self.format_note = QLabel(
            'Til avklaring betyr ikke at filen må konverteres. '
            'Formatvurderingen er uavhengig av Arkades historiske RAF-klassifisering '
            'og erstatter ikke godkjenning eller avtale om avlevering.'
        )
        self.format_note.setWordWrap(True)
        layout.insertWidget(6, self.format_note)
        self.format_policy_combo.currentIndexChanged.connect(self._a4_change_policy)
        self.format_status_combo.currentIndexChanged.connect(self._a4_filter_pronom)
        self.format_search.textChanged.connect(self._a4_filter_pronom)
        table = self._trees['PRONOM']
        table.setHeaderLabels((
            'Uttrekk', 'Format-ID / PUID', 'Filtype', 'Versjon',
            'Antall', 'Arkade RAF-220301 (historisk)', 'Valgt regelprofil (uavhengig)',
        ))
        table.headerItem().setToolTip(5, 'Beholdt historisk klassifisering fra Arkade 5; endres ikke ved profilbytte.')
        table.headerItem().setToolTip(6, 'Ny sammenligning av PUID mot valgt datert profil; ingen depotgodkjenning.')

    def _a4_select_initial_policy(self):
        saved = str(self._a4_settings.value('qt/format_policy_path', '__default__') or '')
        if saved == '__default__':
            # The default is an explicitly dated reference copy, never a live online rule.
            chosen = next((p for p in self._a4_profiles
                           if p.policy_id.startswith('nasjonalarkivet_')), None)
            saved = str(chosen.path) if chosen is not None else ''
        index = self.format_policy_combo.findData(saved)
        if index < 0 and saved:
            try:
                policy = load_format_policy(saved)
                self.format_policy_combo.addItem(policy.label, str(policy.path))
                index = self.format_policy_combo.count() - 1
            except (OSError, ValueError):
                # Do not silently replace a missing user-selected profile.
                self._a5_missing_policy_warning = (
                    'Tidligere valgt profil mangler eller er ugyldig: ' + saved
                    + '. Den er ikke erstattet automatisk.'
                )
                index = 0
        self.format_policy_combo.blockSignals(True)
        self.format_policy_combo.setCurrentIndex(max(0, index))
        self.format_policy_combo.blockSignals(False)
        self._a4_change_policy(persist=False)

    def _a4_browse_policy(self):
        name, _ = QFileDialog.getOpenFileName(
            self, 'Velg versjonert formatregelprofil',
            str(FORMAT_PROFILE_DIR), 'JSON (*.json)',
        )
        if not name:
            return
        try:
            policy = load_format_policy(name)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Ugyldig formatregelprofil', str(exc))
            return
        candidate = str(policy.path)
        index = self.format_policy_combo.findData(candidate)
        if index < 0:
            self.format_policy_combo.addItem(policy.label, candidate)
            index = self.format_policy_combo.count() - 1
        self.format_policy_combo.setCurrentIndex(index)

    def _a4_change_policy(self, _index=None, *, persist=True):
        path = str(self.format_policy_combo.currentData() or '')
        if path:
            try:
                self._a4_format_policy = load_format_policy(path)
            except (OSError, ValueError) as exc:
                # Never leave prior acceptance labels visible for a corrupt or
                # replaced profile. Revert to explicit no-assessment status.
                self._a4_format_policy = None
                self._a5_missing_policy_warning = 'Valgt profil kunne ikke leses. Ingen vurdering foretas.'
                self.format_policy_combo.blockSignals(True)
                self.format_policy_combo.setCurrentIndex(0)
                self.format_policy_combo.blockSignals(False)
                if persist:
                    self._a4_settings.setValue('qt/format_policy_path', '')
                if self._a4_ready:
                    self._a4_assess_pronom()
                QMessageBox.warning(self, 'Kan ikke bruke formatprofil', str(exc))
                return
        else:
            self._a4_format_policy = None
        if persist or path:
            self._a5_missing_policy_warning = ''
        if persist:
            self._a4_settings.setValue('qt/format_policy_path', path)
        if self._a4_ready:
            self._a4_assess_pronom()

    def _a4_make_context_actions(self):
        """Rehome existing global footer buttons into common/context toolbars."""
        outer = self.layout()
        expected = set(_COMMON_ACTIONS)
        for titles in _CONTEXT_ACTIONS.values():
            expected.update(titles)
        recovered: dict[str, QPushButton] = {}
        for index in range(outer.count() - 1, -1, -1):
            entry = outer.itemAt(index)
            layout = entry.layout() if entry is not None else None
            if not isinstance(layout, QHBoxLayout):
                continue
            matched = any(
                (child.widget() is not None
                 and isinstance(child.widget(), QPushButton)
                 and child.widget().text() in expected)
                for n in range(layout.count())
                for child in (layout.itemAt(n),)
            )
            if not matched:
                continue
            outer.takeAt(index)
            while layout.count():
                item = layout.takeAt(0)
                button = item.widget()
                if isinstance(button, QPushButton) and button.text() in expected:
                    recovered[button.text()] = button
            layout.deleteLater()

        self._a4_action_buttons = recovered
        common = QHBoxLayout()
        common.setSpacing(6)
        for label in _COMMON_ACTIONS:
            button = recovered.get(label)
            if button is not None:
                button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                common.addWidget(button)
        common.addStretch(1)
        outer.insertLayout(2, common)

        context = QHBoxLayout()
        context.setSpacing(6)
        for label in (
            'Åpne kildefil', 'Vurder periode…', 'Velg KDRS-evidens…',
            'Lag rapport / samlerapport…', 'Klassisk uttrekksoversikt…',
        ):
            button = recovered.get(label)
            if button is not None:
                button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                context.addWidget(button)
        context.addStretch(1)
        outer.addLayout(context)
        self.tabs.currentChanged.connect(self._a4_apply_context_actions)
        self.tabs.currentChanged.connect(self._a5_select_first_result)

    def _a5_select_first_result(self, _index=None):
        """Show the first actual row on first visit; preserve a user's own selection.

        Result tabs without a table (annual data/depot review) are unaffected.
        Hidden/placeholder rows are never treated as selected evidence.
        """
        tab = self.tabs.tabText(self.tabs.currentIndex())
        table = self._trees.get(tab)
        if table is None:
            return
        current = table.currentItem()
        if (current is not None and not current.isHidden()
                and not current.text(0).startswith(('Ingen lagret evidens',
                                                    'Ingen tilgjengelig Work'))):
            return
        for index in range(table.topLevelItemCount()):
            row = table.topLevelItem(index)
            if row.isHidden() or row.text(0).startswith(('Ingen lagret evidens',
                                                         'Ingen tilgjengelig Work')):
                continue
            table.setCurrentItem(row)
            self._show_detail(tab)
            return
        # No real row: do not show stale details from an earlier selection.
        self._details[tab].clear()

    def _a4_apply_context_actions(self, _index=None):
        active = self.tabs.tabText(self.tabs.currentIndex())
        wanted = set(_CONTEXT_ACTIONS.get(active, ())) | set(_COMMON_ACTIONS)
        for title, button in self._a4_action_buttons.items():
            if title == 'Åpne kildefil':
                button.setText('Åpne rapport' if active == 'Depotrapporter' else 'Åpne kildefil')
            button.setVisible(title in wanted)

    def refresh(self):
        super().refresh()
        if getattr(self, '_a4_ready', False):
            self._a53_enrich_result_tables()
            self._a56_configure_columns()
            self._a4_assess_pronom()
            self._a5_select_first_result()
            self._a53_schedule_splitter()

    def _a56_configure_columns(self):
        """Make test titles readable without hiding IDs, source or status.

        Columns remain interactively resizable. In the new side-by-side tabs
        repeated extraction labels are shortened visually, never in the data.
        """
        widths = {
            'Tekniske kontroller': {0: 200, 1: 82, 2: 390, 3: 115, 4: 88, 5: 105, 6: 95},
            'Arkade 5': {0: 165, 1: 65, 2: 335, 3: 74, 4: 68, 5: 170},
            'PRONOM': {0: 148, 1: 104, 2: 207, 3: 76, 4: 74, 5: 115, 6: 175},
            'Periodevurdering': {0: 148, 1: 185, 2: 103, 3: 126, 4: 116, 5: 118},
        }
        for tab, columns in widths.items():
            tree = self._trees.get(tab)
            if tree is None:
                continue
            # The inherited first column uses ResizeToContents: without
            # switching to Interactive it ignores our narrower side-panel
            # width and consumes most of the available horizontal space.
            tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            for index, size in columns.items():
                if index < tree.columnCount():
                    tree.setColumnWidth(index, size)
            # Full values stay accessible when a narrow panel elides the text.
            for i in range(tree.topLevelItemCount()):
                row = tree.topLevelItem(i)
                for index in ((0, 2) if tab != 'Periodevurdering' else (0, 1)):
                    if index < tree.columnCount():
                        row.setToolTip(index, row.text(index))

    def _a53_enrich_result_tables(self):
        """Presentation-only names and saved Arkade tests when raw JSON is too big.

        This never promotes an external test to a DWM master control, and
        never treats import presence alone as proof that a test executed.
        """
        table = self._trees['Tekniske kontroller']
        table.setHeaderLabels((
            'Uttrekk', 'Test-ID', 'Testnavn', 'Noark-punkt',
            'Status', 'Kontroller', 'Avvik',
        ))
        names = load_technical_test_names()
        for index in range(table.topLevelItemCount()):
            item = table.topLevelItem(index)
            if item.text(0).startswith('Ingen lagret evidens'):
                continue
            # The base refresh has just created six-column rows.
            original = [item.text(col) for col in range(6)]
            details = item.data(0, DETAIL_ROLE)
            name = technical_test_name(details, original[1], names=names)
            for col, value in enumerate((original[0], original[1], name, *original[2:])):
                item.setText(col, value)
            item.setToolTip(2, 'Testnavn fra DWM sin Noark 5-katalog.' if name in names.values()
                            else 'Testnavn er ikke dokumentert i gjeldende katalog.')
            if isinstance(details, dict):
                derived = dict(details)
                derived['testnavn_fra_testkatalog'] = name
                item.setData(0, DETAIL_ROLE, derived)

        arkade_table = self._trees['Arkade 5']
        real = any(not arkade_table.topLevelItem(i).text(0).startswith('Ingen lagret evidens')
                   for i in range(arkade_table.topLevelItemCount()))
        if real:
            return
        # Some full normalized Arkade reports exceed the bounded JSON viewer;
        # saved depot report coverage already has independently sourced test rows.
        recovered = arkade_tests_from_depot(self._snapshots)
        if not recovered:
            registered = sum(
                len((((shot.depot or {}).get('external_validation') or {}).get('arkade5') or {}).get('imports') or [])
                for shot in self._snapshots
            )
            if registered:
                arkade_table.clear()
                self._row('Arkade 5', (
                    f'Ingen lagret evidens for Arkade-tester ({registered} import(er) registrert)',
                    '', '', 'Ukjent', '', ''), details={
                        'opplysning': 'Importregistrering er ikke bevis for at en bestemt test er utført.',
                        'importer': registered,
                        'handling': 'Kontroller lagret Arkade-normalisering og depotrapport.',
                    })
            return
        arkade_table.clear()
        self._details['Arkade 5'].clear()
        for record in recovered:
            self._row('Arkade 5', (
                record['job'].name, record['test_id'], record['title'],
                record['status'], record['errors'], record['import_id'],
            ), details=record['details'], file=record['file'])

    def _a4_assess_pronom(self):
        table = self._trees['PRONOM']
        policy = self._a4_format_policy
        self._a4_format_rows = []
        import_cache = {}
        for i in range(table.topLevelItemCount()):
            item = table.topLevelItem(i)
            if item.text(0).startswith('Ingen lagret evidens'):
                item.setText(6, '')
                item.setData(0, _FORMAT_STATUS_ROLE, '')
                continue
            original = item.data(0, _ORIGINAL_DETAIL_ROLE)
            if original is None:
                original = item.data(0, DETAIL_ROLE)
                item.setData(0, _ORIGINAL_DETAIL_ROLE, original)
            decision = evaluate_puid(item.text(1), policy)
            item.setText(6, decision.label)
            item.setToolTip(6, decision.explanation)
            item.setData(0, _FORMAT_STATUS_ROLE, decision.status)
            base = dict(original) if isinstance(original, dict) else {'observation': original}
            import_id = str(base.get('import_id') or '')
            path = str(item.data(0, PATH_ROLE) or '')
            cache_key = (path, import_id)
            if cache_key not in import_cache:
                import_cache[cache_key] = read_pronom_import_context(path, import_id)
            source = import_cache[cache_key]
            base['formatvurdering'] = {
                'puid': decision.puid,
                'status': decision.status,
                'visning': decision.label,
                'begrunnelse': decision.explanation,
                'matched_rule': (decision.matched_rule.__dict__
                                 if decision.matched_rule is not None else None),
                'regelprofil': policy.provenance() if policy else None,
                'merking': 'Kun avledet visning – original PRONOM/Arkade-evidens er uendret',
            }
            base['historisk_arkade_raf'] = {
                'klassifisering': item.text(5),
                'kilde': 'Arkade 5 / Siegfried – RAF-220301',
                'import_id': import_id,
                'importert_at': source['imported_at'] or 'Ikke oppgitt',
                'pronom_kildefil': source['original_csv'] or 'Ikke oppgitt',
                'pronom_kilde_sha256': source['original_csv_sha256'] or 'Ikke oppgitt',
                'testdato': 'Ikke dokumentert i PRONOM-statistikkens importmetadata',
            }
            item.setData(0, DETAIL_ROLE, base)
            item.setToolTip(5, f"Historisk Arkade RAF: {item.text(5)}\n"
                           f"Import: {import_id or 'Ukjent'}\n"
                           f"Importert: {source['imported_at'] or 'Ikke oppgitt'} (ikke testdato)")
            self._a4_format_rows.append((item, {
                'job': item.text(0),
                'format_id': item.text(1),
                'file_type': item.text(2),
                'version': item.text(3),
                'count': item.text(4),
                'raf': item.text(5),
                'evidence_source': import_id,
                'imported_at': source['imported_at'],
                'original_csv': source['original_csv'],
                'original_csv_sha256': source['original_csv_sha256'],
            }))
        self._a4_filter_pronom()
        if table.currentItem() is not None:
            self._show_detail('PRONOM')

    def _a4_filter_pronom(self, _ignored=None):
        if not getattr(self, '_a4_ready', False):
            return
        status = str(self.format_status_combo.currentData() or '')
        needle = self.format_search.text().strip().casefold()
        visible = 0
        counts = []
        dates = []
        for item, row in self._a4_format_rows:
            item_status = item.data(0, _FORMAT_STATUS_ROLE)
            matches = (not status or status == item_status) and (
                not needle or any(needle in item.text(col).casefold()
                                  for col in range(item.columnCount()))
            )
            item.setHidden(not matches)
            if matches:
                visible += 1
                counts.append({'format_id': row['format_id'], 'count': row['count']})
                dates.append(row['imported_at'])
        table = self._trees['PRONOM']
        for index in range(table.topLevelItemCount()):
            item = table.topLevelItem(index)
            if item.text(0).startswith('Ingen lagret evidens'):
                item.setHidden(bool(status or needle))
        summary = summarize_format_assessments(counts, self._a4_format_policy)
        statuses = summary['statuses']
        accepted = statuses[STATUS_ACCEPTED]['files']
        review = statuses[STATUS_CLARIFY]['files']
        unknown = statuses[STATUS_UNIDENTIFIED]['files']
        unevaluated = statuses[STATUS_NOT_ASSESSED]['files']
        self.format_summary.setText(
            f'Viser {visible} av {len(self._a4_format_rows)} formatgrupper (tall nedenfor gjelder viste rader). '
            f'Akseptert: {accepted} filer | Til avklaring: {review} '
            f'| Ikke identifisert: {unknown} | Ikke vurdert: {unevaluated}.'
        )
        arkade, selected = comparison_labels(self._a4_format_policy, dates)
        self.format_arkade_source.setText(arkade)
        if self._a5_missing_policy_warning:
            selected += '  |  ' + self._a5_missing_policy_warning
        self.format_profile_source.setText(selected)

    def _a5_show_sources(self):
        policy = self._a4_format_policy
        table = self._trees['PRONOM']
        item = table.currentItem()
        record = item.data(0, DETAIL_ROLE) if item is not None else None
        source = record.get('historisk_arkade_raf', {}) if isinstance(record, dict) else {}
        if source:
            arkade_info = (
                f"Arkade import-ID: {source.get('import_id') or 'Ikke oppgitt'}\n"
                f"Importert: {source.get('importert_at') or 'Ikke oppgitt'} (ikke testdato)\n"
                f"PRONOM CSV: {source.get('pronom_kildefil') or 'Ikke oppgitt'}\n"
                f"CSV SHA-256: {source.get('pronom_kilde_sha256') or 'Ikke oppgitt'}"
            )
        else:
            arkade_info = 'Velg en PRONOM-rad for import-ID, importdato og kildefil.'
        if policy is None:
            rule_info = 'Ingen profil valgt. Ingen selvstendig formatvurdering utføres.'
        else:
            rule_info = (
                f'Tittel: {policy.title}\nUtgave: {policy.edition}\n'
                f'Datert kopi: {policy.captured_at} (ikke ikrafttredelsesdato)\n'
                f'Myndighet / kilde: {policy.authority}\n'
                f'Kilde-URL: {policy.source_url}\nProfil SHA-256: {policy.sha256}'
            )
        QMessageBox.information(
            self, 'PRONOM – to uavhengige kilder',
            'A · Arkade 5 / RAF-220301 (historisk kildevurdering)\n'
            + arkade_info + '\n\nB · Valgt regelprofil (ny PUID-sammenligning)\n'
            + rule_info + '\n\nIngen av disse vurderingene godkjenner hele uttrekket.'
        )

    def _a4_export_pronom(self):
        if not self._a4_format_rows:
            QMessageBox.information(self, 'Formatvurdering', 'Ingen formatstatistikk å eksportere.')
            return
        settings = self._a4_settings
        previous = str(settings.value('qt/last_report_output_dir', '') or '')
        folder = Path(previous) if previous and Path(previous).is_dir() else Path.home()
        filename, _ = QFileDialog.getSaveFileName(
            self, 'Eksporter vist PRONOM-formatvurdering',
            str(folder / 'dwm-formatvurdering.csv'), 'CSV (*.csv)',
        )
        if not filename:
            return
        target = Path(filename)
        if not target.suffix:
            target = target.with_suffix('.csv')
        overwrite = False
        if target.exists():
            confirmation = QMessageBox.question(
                self, 'Eksisterende eksportfil', f'Overskrive eksisterende fil?\n{target}',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirmation != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        rows = [row for item, row in self._a4_format_rows if not item.isHidden()]
        try:
            export_comparison_csv(target, rows, self._a4_format_policy, overwrite=overwrite)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Kan ikke eksportere formatvurdering', str(exc))
            return
        settings.setValue('qt/last_report_output_dir', str(target.parent))
        QMessageBox.information(self, 'Formatvurdering', f'Eksportert {len(rows)} rader til:\n{target}')
