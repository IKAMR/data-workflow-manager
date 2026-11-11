"""v0.1.10-a4: source-neutral PRONOM format assessment and contextual actions.

No changes are made to normalized Arkade/Siegfried evidence, Noark5 source,
Work documents, AIP or historical reports. Only an explicit CSV export writes.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSizePolicy,
)

from app.format_policy_v0110_a4 import (
    FORMAT_PROFILE_DIR, STATUS_ACCEPTED, STATUS_CLARIFY,
    STATUS_UNIDENTIFIED, STATUS_NOT_ASSESSED, STATUS_LABELS,
    discover_format_policies, evaluate_puid, export_format_assessments_csv,
    load_format_policy, summarize_format_assessments,
)
from .result_center_v018_a13 import DETAIL_ROLE
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


class ResultCenterWindow(_PreviousResultCenter):
    """Apply a selectable, dated institutional policy over untouched PUID evidence."""

    def __init__(self, *args, **kwargs):
        self._a4_ready = False
        self._a4_settings = QSettings('IKAMR', 'DWM-Qt')
        self._a4_format_rows = []
        self._a4_format_policy = None
        super().__init__(*args, **kwargs)
        self._a4_make_policy_controls()
        self._a4_make_context_actions()
        self._a4_ready = True
        self._a4_select_initial_policy()
        self._a4_apply_context_actions()
        self._a4_assess_pronom()

    def _a4_make_policy_controls(self):
        page = self._pages['PRONOM']
        layout = page.layout()
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
        layout.insertLayout(0, first)

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
        export.setToolTip('Eksporter vist formatstatistikk med profilens kilde og SHA-256.')
        export.clicked.connect(self._a4_export_pronom)
        controls.addWidget(export)
        layout.insertLayout(1, controls)

        self.format_summary = QLabel()
        self.format_summary.setWordWrap(True)
        layout.insertWidget(2, self.format_summary)
        self.format_note = QLabel(
            'Til avklaring betyr ikke at filen må konverteres. '
            'Formatvurderingen er uavhengig av Arkades historiske RAF-klassifisering '
            'og erstatter ikke godkjenning eller avtale om avlevering.'
        )
        self.format_note.setWordWrap(True)
        layout.insertWidget(3, self.format_note)
        self.format_policy_combo.currentIndexChanged.connect(self._a4_change_policy)
        self.format_status_combo.currentIndexChanged.connect(self._a4_filter_pronom)
        self.format_search.textChanged.connect(self._a4_filter_pronom)
        table = self._trees['PRONOM']
        table.setHeaderLabels((
            'Uttrekk', 'Format-ID / PUID', 'Filtype', 'Versjon',
            'Antall', 'RAF (Arkade)', 'Formatvurdering',
        ))

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
                self.format_summary.setText(
                    'Valgt formatprofil kunne ikke leses: ' + saved
                    + '. Ingen nye godkjenningsvurderinger blir foretatt.'
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
        if persist:
            self._a4_settings.setValue('qt/format_policy_path', path)
        if self._a4_ready:
            self._a4_assess_pronom()

    def _a4_make_context_actions(self):
        """Rehome the existing global footer buttons into common/context toolbars.

        The a19 result center inherited two rows of seven global buttons from
        a13. This adapts their visibility without duplicating or rewiring them.
        """
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
        outer.insertLayout(2, common)  # Shared actions just above the tab content.

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
        outer.addLayout(context)  # Only actions of the active tab are shown.
        self.tabs.currentChanged.connect(self._a4_apply_context_actions)

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
            self._a4_assess_pronom()

    def _a4_assess_pronom(self):
        table = self._trees['PRONOM']
        policy = self._a4_format_policy
        self._a4_format_rows = []
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
            item.setData(0, DETAIL_ROLE, base)
            self._a4_format_rows.append((item, {
                'job': item.text(0),
                'format_id': item.text(1),
                'file_type': item.text(2),
                'version': item.text(3),
                'count': item.text(4),
                'raf': item.text(5),
                'evidence_source': str(base.get('import_id', '')),
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
        for item, row in self._a4_format_rows:
            item_status = item.data(0, _FORMAT_STATUS_ROLE)
            matches = (not status or status == item_status) and (
                not needle or any(needle in item.text(col).casefold()
                                  for col in range(item.columnCount()))
            )
            item.setHidden(not matches)
            visible += bool(matches)
            counts.append({'format_id': row['format_id'], 'count': row['count']})
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
        profile = (f'{self._a4_format_policy.label} | SHA-256: '
                   f'{self._a4_format_policy.sha256[:12]}…'
                   if self._a4_format_policy is not None else 'Ingen formatregelprofil')
        self.format_summary.setText(
            f'{visible} av {len(self._a4_format_rows)} formatgrupper. '
            f'Akseptert: {accepted} filer | Til avklaring: {review} '
            f'| Ikke identifisert: {unknown} | Ikke vurdert: {unevaluated}. '
            f'Regelprofil: {profile}. '
            'Vurderingene bygger på nåværende valgte liste, ikke på Arkades RAF-resultat.'
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
            export_format_assessments_csv(target, rows, self._a4_format_policy,
                                          overwrite=overwrite)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Kan ikke eksportere formatvurdering', str(exc))
            return
        settings.setValue('qt/last_report_output_dir', str(target.parent))
        QMessageBox.information(self, 'Formatvurdering', f'Eksportert {len(rows)} rader til:\n{target}')
