"""v0.1.10-a1 Setup: a generic storage-profile selector with read-only preview."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
)

from app.storage_profiles_v0110_a1 import (
    DEFAULT_STORAGE_PROFILE, storage_profile_choices,
)
from gui_qt.setup_v018_a7 import DwmSetupDialog as _PreviousSetupDialog, _note


class DwmSetupDialog(_PreviousSetupDialog):
    """Keep all legacy Setup pages while providing explicit storage-profile setup."""

    def _build_storage_tab(self):
        content, form = self._tab('Mapper og Work')
        self.storage_profile = QComboBox()
        active = str(self.settings.get('storage_layout_profile', DEFAULT_STORAGE_PROFILE) or DEFAULT_STORAGE_PROFILE)
        self._storage_profile_choices = storage_profile_choices(include_legacy=active == 'none')
        for profile in self._storage_profile_choices:
            self.storage_profile.addItem(profile.label, profile.profile_id)
        index = self.storage_profile.findData(active)
        if index < 0:
            # An unfamiliar saved choice is preserved visibly, not rewritten.
            self.storage_profile.addItem('Ukjent eldre profil (' + active + ')', active)
            index = self.storage_profile.count() - 1
        self.storage_profile.setCurrentIndex(index)
        form.addRow('Standard lagringsprofil for nye jobber:', self.storage_profile)
        form.addRow('', _note(
            'Standard – enkel mappestruktur er standard for nye oppsett. '
            'De andre profilene beskriver fysisk mappeorganisering, ikke nye Core-roller. '
            'Arkivskaperorientert er en illustrasjon, ikke en bekreftet IKAR-standard.'
        ))
        self.profile_description = QLabel()
        self.profile_description.setWordWrap(True)
        form.addRow('Profilbeskrivelse:', self.profile_description)
        self.profile_preview = QPlainTextEdit()
        self.profile_preview.setReadOnly(True)
        self.profile_preview.setMinimumHeight(165)
        self.profile_preview.setMaximumHeight(235)
        form.addRow('Eksempel på mappestruktur:', self.profile_preview)
        form.addRow('', _note(
            'Forhåndsvisningen er bare et eksempel. Kildemappen flyttes aldri. '
            'Eksisterende jobber og Work-referanser beholdes; ny profil brukes '
            'kun til forslag for nye jobber. AIP opprettes ikke ved profilvalg.'
        ))
        # Retain the existing global DWM level without changing its semantics.
        self.work_subfolder = QLineEdit(str(self.settings.get('app_work_subfolder', 'dwm') or ''))
        self.storage_profile.currentIndexChanged.connect(lambda _index: self._update_profile_preview())
        self.work_subfolder.textChanged.connect(lambda _text: self._update_profile_preview())
        self._update_profile_preview()
        form.addRow('DWM-undermappe under Work - operations:', self.work_subfolder)
        form.addRow('', _note(
            'Dette er en global regel, normalt dwm. '
            'Jobblistens egen undermapperegel beholdes i Jobber-panelet. '
            'Endring kan endre hvor eldre jobber finner resultater; ingen data flyttes.'
        ))

    def _update_profile_preview(self):
        current = str(self.storage_profile.currentData() or '')
        item = next((p for p in self._storage_profile_choices if p.profile_id == current), None)
        if item is None:
            self.profile_description.setText('Ukjent eldre profil. Velg en av de definerte profilene for nye jobber.')
            self.profile_preview.setPlainText('Ingen kjent struktur kan vises.')
        else:
            self.profile_description.setText(item.description)
            subfolder = self.work_subfolder.text().strip() if hasattr(self, 'work_subfolder') else 'dwm'
            example = item.example_tree.replace('dwm/', (subfolder + '/') if subfolder else '(ingen app-undermappe)')
            self.profile_preview.setPlainText(example)

    def _updates(self) -> dict:
        result = super()._updates()
        result['storage_layout_profile'] = str(self.storage_profile.currentData() or '').strip()
        return result

    def _save(self):
        current = str(self.settings.get('storage_layout_profile', DEFAULT_STORAGE_PROFILE) or DEFAULT_STORAGE_PROFILE)
        chosen = str(self.storage_profile.currentData() or '')
        if chosen != current:
            answer = QMessageBox.question(
                self, 'Endre standard lagringsprofil',
                'Den nye profilen gjelder forslag til NYE jobber. '
                'Eksisterende jobber, Work, Source og AIP blir ikke flyttet '
                'eller endret. Vil du lagre dette profilvalget?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        super()._save()
