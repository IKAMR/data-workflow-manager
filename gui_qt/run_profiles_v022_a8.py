"""a8: per-job run profile chooser shared by Simple and Advanced UI.

No startup timers, filters, new execution engine, or hidden migration.
"""
from __future__ import annotations

import json

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout)

from app.run_profiles_v022_a8 import (available_profiles, selected_default,
    toggle_arkade, profile_controls, save_custom_profile)
from app.workflow_dependencies_v022_a7 import dependency_label
from settings import save_config


class RunProfileDialog(QDialog):
    def __init__(self, parent, *, settings: dict, job_id: str | None,
                 current_operations=()):
        super().__init__(parent)
        self.settings = settings
        self.job_id = job_id
        self.profiles = available_profiles(settings)
        self.setWindowTitle('Kjøreprofiler – ' + (job_id or 'standard for nye jobber'))
        self.setMinimumWidth(650)
        layout = QVBoxLayout(self)
        intro = QLabel('Velg en profil. Arkade Noark og Arkade PRONOM kan velges hver for seg. '
                       'Endringer kjøres ikke før du starter jobben.', self)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.chooser = QComboBox(self)
        for profile in self.profiles:
            self.chooser.addItem(profile.name, profile.profile_id)
        wanted = selected_default(settings).profile_id
        current_operations = tuple(current_operations)
        matching = next((p for p in self.profiles
                         if p.operation_ids == current_operations), None)
        if matching is not None:
            wanted = matching.profile_id
        self.chooser.setCurrentIndex(next((i for i, p in enumerate(self.profiles)
                                           if p.profile_id == wanted), 0))
        layout.addWidget(self.chooser)
        self.arkade_noark = QCheckBox('Arkade 5 – Noark 5-test (A150)', self)
        self.arkade_pronom = QCheckBox('Arkade 5 – PRONOM (A160)', self)
        layout.addWidget(self.arkade_noark)
        layout.addWidget(self.arkade_pronom)
        self.operations = QTextEdit(self)
        self.operations.setReadOnly(True)
        self.operations.setMinimumHeight(220)
        layout.addWidget(self.operations)
        self.set_default = QCheckBox('Bruk denne profilen som standard for nye jobber', self)
        layout.addWidget(self.set_default)
        custom_row = QHBoxLayout()
        self.custom_name = QLineEdit(self)
        self.custom_name.setPlaceholderText('Navn på egen profil')
        self.save_custom = QPushButton('Lagre som egen profil…', self)
        custom_row.addWidget(self.custom_name)
        custom_row.addWidget(self.save_custom)
        layout.addLayout(custom_row)
        footer = QDialogButtonBox(self)
        self.apply = footer.addButton('Bruk på valgt jobb' if job_id else 'Lagre standard',
                                      QDialogButtonBox.ButtonRole.AcceptRole)
        footer.addButton(QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(footer)
        footer.accepted.connect(self.accept)
        footer.rejected.connect(self.reject)
        self.chooser.currentIndexChanged.connect(self._changed)
        self.arkade_noark.toggled.connect(self._preview)
        self.arkade_pronom.toggled.connect(self._preview)
        self.save_custom.clicked.connect(self._save_custom)
        self._changed()

    def _changed(self, *_unused):
        profile = self.profiles[self.chooser.currentIndex()]
        noark, pronom = profile_controls(profile)
        for checkbox, checked in ((self.arkade_noark, noark),
                                  (self.arkade_pronom, pronom)):
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)
        self._preview()

    def selected(self):
        return toggle_arkade(self.profiles[self.chooser.currentIndex()],
                             noark=self.arkade_noark.isChecked(),
                             pronom=self.arkade_pronom.isChecked())

    def _preview(self, *_unused):
        profile = self.selected()
        self.operations.setPlainText(profile.description + '\n\n' + '\n'.join(
            f'{i:02d}  {dependency_label(op)}  {op}'
            for i, op in enumerate(profile.operation_ids, 1)))

    def _save_custom(self):
        name = self.custom_name.text().strip()
        if not name:
            QMessageBox.warning(self, 'Kjøreprofil', 'Skriv et navn for profilen.')
            return
        try:
            changes = save_custom_profile(self.settings, name, self.selected().operation_ids)
            save_config(changes)
            self.settings.update(changes)
            self.profiles = available_profiles(self.settings)
            new_profile = self.profiles[-1]
            self.chooser.addItem(new_profile.name, new_profile.profile_id)
            self.chooser.setCurrentIndex(len(self.profiles) - 1)
            QMessageBox.information(self, 'Kjøreprofil', 'Profilen er lagret. Eksisterende jobber er uendret.')
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Kjøreprofil', str(exc))


def open_run_profile_dialog(window) -> bool:
    if window._worker is not None or window.api.running:
        QMessageBox.warning(window, 'Kjøreprofiler', 'Avslutt kjøringen før du endrer profil.')
        return False
    # Do not auto-register drafts from a profile editor; selection without a
    # job changes only the default for future jobs.
    job_id = getattr(window, '_active_id', None)
    settings = window.api.settings
    current = tuple(op.operation_id for op in window.api.job_details(job_id).operations) if job_id else ()
    dialog = RunProfileDialog(window, settings=settings, job_id=job_id,
                              current_operations=current)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    selection = dialog.selected()
    if dialog.set_default.isChecked() or not job_id:
        # Modified Arkade checkbox combination is a custom template and must
        # be saved explicitly; never label it as the unchanged builtin.
        source = dialog.profiles[dialog.chooser.currentIndex()]
        if selection.operation_ids != source.operation_ids:
            QMessageBox.warning(window, 'Kjøreprofil',
                'Lagre det tilpassede oppsettet som egen profil før det settes som standard.')
            return False
        save_config({'noark5_default_run_profile': source.profile_id})
        settings['noark5_default_run_profile'] = source.profile_id
    if not job_id:
        QMessageBox.information(window, 'Kjøreprofil',
            'Standardprofil lagret. Den brukes for nye jobber, ikke eksisterende jobber.')
        return True
    try:
        detail = window.api.job_details(job_id)
        job = detail.job
        current = tuple(op.operation_id for op in detail.operations)
        if current == selection.operation_ids:
            return True
        # Block changing previously started jobs. A deliberate fresh run must
        # be configured on a new job or through existing explicit UI tools.
        cursor = int(getattr(job, 'next_operation_index', 0) or 0)
        if cursor or float(getattr(job, 'progress', 0) or 0):
            raise ValueError('Jobben har kjøringshistorikk. Profilbytte her er kun tillatt før første kjøring.')
        if window._active_id != job_id:
            raise ValueError('Aktiv jobb ble endret under profilvalget.')
        window.api.set_workflow(job_id, selection.operation_ids)
        if window.api.workspace().job_list_path:
            window.api.save_job_list()
        if getattr(window, '_basic_active', False):
            # Reflect profile's independent external controls in Basic's
            # existing checkboxes; do not trigger plan regeneration here.
            checkboxes = getattr(window, 'basic_option_checks', {})
            if checkboxes:
                chosen = set(selection.operation_ids)
                checked = {'dwm': 'run_noark5_xpath_tests_2026' in chosen,
                           'siegfried': 'siegfried_pronom_identification' in chosen,
                           'arkade_noark5': 'arkade5_noark5_test' in chosen,
                           'arkade_pronom': 'arkade5_pronom_analysis' in chosen}
                window._setting_basic_workflow = True
                try:
                    for key, box in checkboxes.items():
                        box.setChecked(checked.get(key, False))
                    window.config.setValue('qt/v0111_basic_options', json.dumps(
                        [key for key in ('dwm','siegfried','arkade_noark5','arkade_pronom')
                         if checked[key]]))
                finally:
                    window._setting_basic_workflow = False
        window._render_key = None
        window._refresh(force=True)
        QMessageBox.information(window, 'Kjøreprofil',
            'Deljobbprofilen er lagret for ' + job_id + '. Ingen kontroll er startet.')
        return True
    except (ValueError, RuntimeError, OSError) as exc:
        QMessageBox.warning(window, 'Kjøreprofil', str(exc))
        return False
