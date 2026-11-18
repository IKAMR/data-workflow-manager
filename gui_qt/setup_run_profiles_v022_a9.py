"""a9: one visible run-profile selector in Setup -> Arbeidsflyt.

Keep the legacy sequence model internally for compatibility with older
clients and saved jobs. New Qt jobs use the exact a9 user default instead.
No edits are written until the existing shared Setup Save button succeeds.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from app.operation_metadata import VISIBILITY_LABELS
from app.run_profiles_v022_a8 import available_profiles, selected_default
from app.run_profiles_v022_a9 import legacy_fallback_sequence
from app.workflow_sequences import load_workflow_sequences
from gui_qt.setup_format_v0111_a2 import DwmSetupDialog as _PreviousSetupDialog
from gui_qt.profile_editor_v022_a9 import RunProfileOrderEditor
from gui_qt.combo_anchor_v022_a10 import anchor_setup_combo


class DwmSetupDialog(_PreviousSetupDialog):
    """Only replace Workflow tab presentation and validated profile fields."""

    def _build_workflow_tab(self):
        _content, form = self._tab('Arbeidsflyt')
        # The old Setup API still references these fields. Keep them as a
        # conservative compatibility bridge, but not as a competing default.
        self.workflow = QComboBox(self)
        self.workflow.hide()  # internal compatibility bridge, never a second visible selector
        self._workflow_has_arkade = {}
        self._a9_old_sequences = tuple(
            seq for seq in load_workflow_sequences(settings=self.settings)
            if seq.profile_id == 'noark5')
        for sequence in self._a9_old_sequences:
            self.workflow.addItem(sequence.name, sequence.sequence_id)
            self._workflow_has_arkade[sequence.sequence_id] = bool(
                set(sequence.operation_ids) & {'arkade5_noark5_test', 'arkade5_pronom_analysis'})

        self._a9_pending = dict(self.settings)
        self._a9_combo = QComboBox(self)
        self._a9_combo.setMinimumWidth(300)
        anchor_setup_combo(self._a9_combo)
        self._a9_combo.currentIndexChanged.connect(self._a9_selection_changed)
        form.addRow('Standard kjøreprofil for nye Noark 5-jobber:', self._a9_combo)
        self._a9_description = QLabel(self)
        self._a9_description.setWordWrap(True)
        form.addRow('', self._a9_description)

        button_row = QWidget(self)
        buttons = QHBoxLayout(button_row)
        buttons.setContentsMargins(0, 0, 0, 0)
        self._a9_edit_button = QPushButton('Rediger deljobber og rekkefølge…', button_row)
        self._a9_edit_button.clicked.connect(self._a9_edit_current)
        buttons.addWidget(self._a9_edit_button)
        buttons.addStretch(1)
        form.addRow('', button_row)

        self.visibility = QComboBox(self)
        anchor_setup_combo(self.visibility)
        for value, label in VISIBILITY_LABELS.items():
            self.visibility.addItem(label, value)
        try:
            level = int(self.settings.get('operation_visibility', 2))
        except (ValueError, TypeError):
            level = 2
        idx = self.visibility.findData(level)
        self.visibility.setCurrentIndex(max(0, idx))
        form.addRow('Vis operasjoner:', self.visibility)
        tip = QLabel('Standardprofilen brukes kun på nye jobber. Hver jobb lagrer en egen '
                     'deljobbliste; eksisterende .n5jobs og Work endres ikke. '
                     'Innebygde profiler er skrivebeskyttet; redigering lager en egen kopi.', self)
        tip.setWordWrap(True)
        form.addRow('', tip)

        self._a9_legacy_toggle = QPushButton('Eldre profiler – vis kompatibilitetslisten', self)
        self._a9_legacy_toggle.setCheckable(True)
        self._a9_legacy_toggle.setChecked(False)
        self._a9_legacy_toggle.setToolTip('Kun eldre forhåndsdefinerte arbeidsflyter, ikke nye standardvalg.')
        form.addRow('', self._a9_legacy_toggle)
        legacy = QWidget(self)
        old_layout = QVBoxLayout(legacy)
        old_layout.setContentsMargins(6, 2, 6, 5)
        old_note = QLabel(
            'Historiske arbeidsflyter beholdes for kompatibilitet og tidligere jobblister. '
            'Dette er ikke en ekstra standardprofilvelger. Nye oppsett velges ovenfor.', legacy)
        old_note.setWordWrap(True)
        old_layout.addWidget(old_note)
        old_names = QLabel('\n'.join('• ' + seq.name for seq in self._a9_old_sequences), legacy)
        old_names.setWordWrap(True)
        old_layout.addWidget(old_names)
        legacy.setVisible(False)
        self._a9_legacy_toggle.toggled.connect(legacy.setVisible)
        form.addRow('', legacy)
        self._a9_refresh_profiles(selected_default(self._a9_pending).profile_id)

    def _a9_refresh_profiles(self, wanted: str):
        self._a9_combo.blockSignals(True)
        self._a9_combo.clear()
        for profile in available_profiles(self._a9_pending):
            self._a9_combo.addItem(profile.name + (' (egen)' if not profile.builtin else ''),
                                  profile.profile_id)
        index = self._a9_combo.findData(wanted)
        self._a9_combo.setCurrentIndex(max(0, index))
        self._a9_combo.blockSignals(False)
        self._a9_selection_changed()

    def _a9_current_profile(self):
        wanted = str(self._a9_combo.currentData() or '')
        return next(p for p in available_profiles(self._a9_pending)
                    if p.profile_id == wanted)

    def _a9_selection_changed(self, _index=None):
        if self._a9_combo.currentIndex() < 0:
            return
        profile = self._a9_current_profile()
        self._a9_description.setText(
            f'{profile.description}\n{len(profile.operation_ids)} deljobber inklusive '
            'automatisk evidens og KS-grunnlag. Arkade Noark og PRONOM kan velges separat '
            'ved redigering. Ingen jobb endres når du velger dette.')
        old_id = legacy_fallback_sequence(profile)
        index = self.workflow.findData(old_id)
        if index >= 0:
            self.workflow.setCurrentIndex(index)

    def _a9_edit_current(self):
        profile = self._a9_current_profile()
        editor = RunProfileOrderEditor(self, settings=self._a9_pending, profile=profile)
        if editor.exec() != QDialog.DialogCode.Accepted or editor.result_edit is None:
            return
        changes = editor.result_edit.changes
        self._a9_pending.update(changes)
        self._a9_refresh_profiles(editor.result_edit.profile_id)
        self._a9_description.setText(self._a9_description.text() +
            '\nEndringen er ikke lagret. Bruk Lagre nederst i Setup for å bekrefte.')

    def _updates(self) -> dict:
        updates = super()._updates()
        # The old bridge is deliberately a conservative fallback. The actual
        # default workflow is the a9 selection, persisted through shared API.
        selected_id = str(self._a9_combo.currentData() or '')
        updates['noark5_default_run_profile'] = selected_id
        updates['noark5_custom_run_profiles'] = list(
            self._a9_pending.get('noark5_custom_run_profiles', []))
        return updates
