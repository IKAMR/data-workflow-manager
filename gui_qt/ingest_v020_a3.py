"""v0.2.0-a3: integrated PySide6 Ingest using the existing depot receive engine.

The Qt page does not spawn the Tk GUI. It does not copy/download/scan data,
create job lists or mutate Work. Only explicit confirmation writes new EMPTY
receipt/extraction folders and the backend's append-only event/audit records.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from app.ingest_controller_v020_a3 import (
    DEFAULT_RECEIVING_SETUP, IngestRequest, available_profiles,
    prepare_ingest, preview_ingest, create_ingest,
)
from settings import load_config, save_config


class IngestPage(QWidget):
    """A resumable form page, with no side effects until an explicit Yes."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setObjectName('v020_a3_ingest_page')
        self._profiles = {}
        self._last_profile_path = None
        self._last_extraction = None
        self._preview_plan = None
        try:
            saved = load_config()
        except (OSError, ValueError, TypeError):
            saved = {}
        if not isinstance(saved, dict):
            saved = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        scroller = QScrollArea(self)
        scroller.setObjectName('v020_a3_ingest_scroll')
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroller)
        content = QWidget(scroller)
        scroller.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 16, 22, 20)
        layout.setSpacing(12)

        heading = QHBoxLayout()
        title = QLabel('Ingest – mottak og uttrekk', content)
        title.setStyleSheet('font-size: 22px; font-weight: 600;')
        heading.addWidget(title)
        heading.addStretch()
        home = QPushButton('Til Startside', content)
        home.clicked.connect(lambda: window.v020_integrated_home())
        heading.addWidget(home)
        layout.addLayout(heading)
        intro = QLabel(
            'Mottak oppretter bare en flat E-FFKK-YYYY-nnnn-mappe. '
            'Uttrekk oppretter en separat søskenmappe med Work-struktur. '
            'Ingen arkivfiler lastes ned, kopieres, pakkes ut, skannes eller flyttes.',
            content,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setVerticalSpacing(11)
        layout.addLayout(form)

        self.mode = QComboBox(content)
        self.mode.setObjectName('v020_a3_ingest_mode')
        self.mode.addItem('Mottak – opprett flat mottaksmappe', 'receipt')
        self.mode.addItem('Uttrekk – opprett separat arbeidsmappe', 'extraction')
        self.mode.currentIndexChanged.connect(self._mode_changed)
        form.addRow('Handling:', self.mode)

        self.xml = QLineEdit(content)
        self.xml.setObjectName('v020_a3_ingest_xml')
        self._add_line(form, 'info.xml (valgfritt):', self.xml,
                       (('Velg…', self._select_xml), ('Bruk LABEL', self._use_xml_label),
                        ('Tøm', lambda: self.xml.clear())))

        self.label = QLineEdit(content)
        self.label.setObjectName('v020_a3_ingest_label')
        self.label.setPlaceholderText('Påkrevd – beholdes som metadata, ikke mappenavn')
        self._add_line(form, 'LABEL:', self.label)

        self.owner = QLineEdit(content)
        self.owner.setObjectName('v020_a3_ingest_owner')
        self.owner.setPlaceholderText('Fire siffer for gjeldende eierkommune')
        self._add_line(form, 'Eierkommune (FFKK):', self.owner)

        self.receipt = QLineEdit(content)
        self.receipt.setObjectName('v020_a3_ingest_receipt')
        self.receipt.setPlaceholderText('E-FFKK-YYYY-nnnn')
        self._add_line(form, 'Mottaksnummer:', self.receipt,
                       (('Neste forslag', self._suggest_number),
                        ('Velg mottak', self._select_existing_receipt)))

        self.disk = QLineEdit(str(saved.get('last_ingest_disk', '') or ''), content)
        self.disk.setObjectName('v020_a3_ingest_disk')
        self._add_line(form, 'Disk / volum:', self.disk,
                       (('Velg disk…', self._select_disk),))

        self.group = QLineEdit(str(saved.get('last_ingest_group', '') or ''), content)
        self.group.setObjectName('v020_a3_ingest_group')
        self.group.setPlaceholderText('Eksisterende arkiv-karantene-nn')
        self._add_line(form, 'Gruppemappe:', self.group,
                       (('Velg gruppe…', self._select_group),))

        self.extraction = QLineEdit(content)
        self.extraction.setObjectName('v020_a3_ingest_extraction')
        self.extraction.setPlaceholderText('FFKK_nnn')
        self._add_line(form, 'Uttrekks-ID (kun Uttrekk):', self.extraction)

        self.unpack_date = QLineEdit(date.today().isoformat(), content)
        self.unpack_date.setObjectName('v020_a3_ingest_date')
        self.unpack_date.setPlaceholderText('YYYY-MM-DD')
        self._add_line(form, 'Dato (kun Uttrekk):', self.unpack_date)

        self.setup_file = QLineEdit(
            str(saved.get('receiving_setup_file') or DEFAULT_RECEIVING_SETUP), content
        )
        self.setup_file.setObjectName('v020_a3_ingest_setup')
        self._add_line(form, 'Depot-setup (JSON):', self.setup_file,
                       (('Velg JSON…', self._select_setup),
                        ('Last inn profiler', self._reload_profiles)))

        self.profile = QComboBox(content)
        self.profile.setObjectName('v020_a3_ingest_profile')
        form.addRow('Mappeprofil:', self.profile)

        presets = QHBoxLayout()
        presets.addWidget(QLabel('Brukerprofil:', content))
        for label_text, callback in (
            ('Åpne profil…', self._open_preset),
            ('Lagre profil', self._save_preset),
            ('Lagre som ny…', self._save_preset_as),
        ):
            button = QPushButton(label_text, content)
            button.clicked.connect(callback)
            presets.addWidget(button)
        presets.addStretch()
        layout.addLayout(presets)
        self.preset_note = QLabel('Ingen lagret mottaksprofil valgt.', content)
        self.preset_note.setWordWrap(True)
        layout.addWidget(self.preset_note)

        layout.addWidget(QLabel('Forhåndsvisning (skrivebeskyttet):', content))
        self.preview = QPlainTextEdit(content)
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(215)
        self.preview.setObjectName('v020_a3_ingest_preview')
        self.preview.setPlaceholderText('Trykk «Vis mappestruktur» før opprettelse.')
        layout.addWidget(self.preview)

        buttons = QHBoxLayout()
        self.preview_button = QPushButton('Vis mappestruktur', content)
        self.preview_button.clicked.connect(self._preview)
        buttons.addWidget(self.preview_button)
        self.create_button = QPushButton('Opprett mottaksmappe…', content)
        self.create_button.setObjectName('v020_a3_ingest_create')
        self.create_button.clicked.connect(self._create)
        buttons.addWidget(self.create_button)
        self.work_button = QPushButton('Gå til eksisterende Work', content)
        self.work_button.setToolTip('Åpner Work-steg på en eksisterende jobb. Ingen automatisk jobbkobling.')
        self.work_button.clicked.connect(self._go_work)
        buttons.addWidget(self.work_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.status = QLabel('', content)
        self.status.setObjectName('v020_a3_ingest_status')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch(1)

        for widget in (self.xml, self.label, self.owner, self.receipt,
                       self.disk, self.group, self.extraction, self.unpack_date,
                       self.setup_file):
            widget.textChanged.connect(self._invalidate)
        self.profile.currentIndexChanged.connect(self._invalidate)
        self._reload_profiles()
        self._mode_changed()
        last = str(saved.get('last_ingest_user_profile_file', '') or '')
        if last and Path(last).is_file():
            try:
                self._apply_preset(last)
            except (OSError, ValueError):
                self.preset_note.setText('Tidligere brukerprofil kunne ikke åpnes. Velg Åpne profil.')

    @staticmethod
    def _add_line(form, title, field, actions=()):
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.addWidget(field, 1)
        for label, callback in actions:
            button = QPushButton(label, row)
            button.clicked.connect(callback)
            line.addWidget(button)
        form.addRow(title, row)

    def _invalidate(self, *_args):
        self._preview_plan = None
        self.preview.clear()
        self.create_button.setEnabled(bool(self._profiles))
        self.status.setText('Innstillinger endret – vis ny mappestruktur før opprettelse.')

    def _mode_changed(self, _index=None):
        is_extraction = self.mode.currentData() == 'extraction'
        self.extraction.setEnabled(is_extraction)
        self.unpack_date.setEnabled(is_extraction)
        self.create_button.setText('Opprett uttrekksmappe…' if is_extraction else
                                   'Opprett mottaksmappe…')
        self._invalidate()

    def _load_request(self):
        return IngestRequest(
            mode=self.mode.currentData(),
            setup_file=self.setup_file.text().strip(),
            profile_id=str(self.profile.currentData() or ''),
            disk=self.disk.text(), group=self.group.text(),
            owner_code=self.owner.text(), receipt_number=self.receipt.text(),
            label=self.label.text(), extraction_id=self.extraction.text(),
            unpack_date=self.unpack_date.text(), info_xml=self.xml.text(),
        )

    def _reload_profiles(self):
        preferred = self.profile.currentData()
        self._profiles = {}
        self.profile.blockSignals(True)
        self.profile.clear()
        try:
            profiles = available_profiles(self.setup_file.text().strip())
            if not profiles:
                raise ValueError('Depot-setup har ingen profiler for gruppert mottak')
            for profile in profiles:
                self._profiles[profile.profile_id] = profile
                self.profile.addItem(profile.name, profile.profile_id)
            idx = self.profile.findData(preferred)
            self.profile.setCurrentIndex(max(0, idx))
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.status.setText('Kunne ikke laste mottaksprofiler: ' + str(error))
        finally:
            self.profile.blockSignals(False)
        self._preview_plan = None
        self.create_button.setEnabled(bool(self._profiles))

    def _select_xml(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Velg info.xml', '',
                                                   'XML (*.xml);;Alle filer (*)')
        if filename:
            self.xml.setText(filename)

    def _use_xml_label(self):
        try:
            from app.receiving_folders import read_info_xml
            data = read_info_xml(self.xml.text().strip())
            label = str(data.get('label') or '').strip()
            if not label:
                raise ValueError('info.xml inneholder ikke LABEL')
            self.label.setText(label)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.warning(self, 'info.xml', str(error))

    def _select_disk(self):
        path = QFileDialog.getExistingDirectory(self, 'Velg karantenedisk', self.disk.text())
        if path:
            self.disk.setText(path)

    def _select_group(self):
        path = QFileDialog.getExistingDirectory(self, 'Velg arkiv-karantene-nn',
                                                self.disk.text())
        if path:
            group = Path(path)
            self.disk.setText(str(group.parent))
            self.group.setText(group.name)

    def _select_existing_receipt(self):
        path = QFileDialog.getExistingDirectory(self,
                        'Velg eksisterende E-FFKK-YYYY-nnnn-mappe', self.disk.text())
        if not path:
            return
        from app.grouped_ingest import RECEIPT
        chosen = Path(path)
        match = RECEIPT.fullmatch(chosen.name.upper())
        if match is None:
            QMessageBox.warning(self, 'Ugyldig mottaksmappe',
                                'Velg en mottaksmappe med navn E-FFKK-YYYY-nnnn.')
            return
        self.disk.setText(str(chosen.parent.parent))
        self.group.setText(chosen.parent.name)
        self.owner.setText(match.group(1))
        self.receipt.setText(chosen.name)
        self.mode.setCurrentIndex(self.mode.findData('extraction'))

    def _select_setup(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Velg depot-setup',
                 self.setup_file.text(), 'JSON (*.json);;Alle filer (*)')
        if filename:
            self.setup_file.setText(filename)
            self._reload_profiles()

    def _suggest_number(self):
        try:
            from app.grouped_ingest import suggest_receipt_number
            profile = self._profiles[str(self.profile.currentData())]
            suggestion = suggest_receipt_number(self.disk.text().strip(), profile,
                                                 self.owner.text().strip())
        except (OSError, ValueError, KeyError, TypeError) as error:
            QMessageBox.warning(self, 'Mottaksnummer', str(error))
            return
        self.receipt.setText(suggestion)
        self.status.setText('Nummerforslaget gjelder bare valgt disk. '
                            'Kontroller depotregisteret og andre disker før opprettelse.')

    def _preview(self):
        self._preview_plan = None
        try:
            plan = prepare_ingest(self._load_request())
            text = preview_ingest(plan)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.preview.setPlainText('Kan ikke opprette plan:\n' + str(error))
            self.status.setText('Ingen mapper opprettet.')
            return None
        self.preview.setPlainText(text)
        self._preview_plan = plan
        self.create_button.setEnabled(True)
        self.status.setText(f'{len(plan.paths)} mapper planlagt. Ingen data endret.')
        return plan

    def _create(self):
        if getattr(self.window, '_worker', None) is not None or self.window.api.running:
            QMessageBox.warning(self, 'Mottak / Ingest',
                                'Avslutt pågående jobbkjøring før mottak opprettes.')
            return
        # Recompute the plan so a previous preview can never authorize stale
        # field values or re-use paths that appeared since the preview.
        plan = self._preview()
        if plan is None:
            return
        answer = QMessageBox.question(
            self, 'Bekreft Mottak / Ingest',
            f'Opprett {len(plan.paths)} tomme mapper?\n\n{plan.root}\n\n'
            f'Mottaksnummer: {plan.receipt_number}\nLABEL: {plan.label}\n\n'
            'Ingen arkivfiler lastes ned, kopieres, flyttes eller skannes.\n'
            'Bekreft at mottaksnummeret er kontrollert mot depotregisteret og andre disker.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            created = create_ingest(plan)
        except Exception as error:
            self._preview_plan = None
            self.create_button.setEnabled(False)
            self.status.setText('Opprettelse feilet – kontroller logg og mapper før nytt forsøk.')
            QMessageBox.critical(self, 'Mottak / Ingest', str(error))
            return
        self._preview_plan = None
        self.create_button.setEnabled(False)  # prevent double submission
        self.preview.setPlainText(preview_ingest(plan) + '\n\nOPPRETTET OG LOGGFØRT')
        self._last_extraction = str(plan.root) if plan.mode == 'extraction' else None
        try:
            save_config({
                'receiving_setup_file': self.setup_file.text().strip(),
                'last_ingest_disk': str(plan.disk),
                'last_ingest_group': plan.group.name,
            })
        except OSError:
            # The canonical creation event has already been written by Core.
            self.status.setText('Mottak opprettet og loggført; kunne ikke lagre brukerens siste valg.')
        else:
            self.status.setText('Opprettet og loggført: ' + str(plan.root))
        next_step = ('\n\nLast ned leveransen manuelt til den flate E-mappen.'
                     if plan.mode == 'receipt' else
                     '\n\nVelg eksisterende jobb i Kontroll og bruk Work-steg. '
                     'Ingen automatisk kobling er opprettet.')
        QMessageBox.information(
            self, 'Mottak / Ingest',
            f'Opprettet {len(created)} mapper:\n{plan.root}\n\n'
            f'Kanonisk hendelseslogg: {plan.audit_path}{next_step}',
        )

    def _go_work(self):
        # The current job is selected manually in the existing workbench.
        # Never silently assign a job's Source, Work or storage paths.
        if hasattr(self.window, 'v020_go_to_work'):
            self.window.v020_go_to_work()

    def _apply_preset(self, filename):
        from app.ingest_saved_profiles import load_ingest_profile
        values = load_ingest_profile(filename)
        self.setup_file.setText(values['setup_file'])
        self._reload_profiles()
        index = self.profile.findData(values['folder_profile_id'])
        if index < 0:
            raise ValueError('Brukerprofilen viser til en ukjent mottaksprofil')
        self.profile.setCurrentIndex(index)
        self.disk.setText(values['disk'])
        self.group.setText(values['group'])
        self.owner.setText(values['owner_code'])
        self.mode.setCurrentIndex(self.mode.findData(
            'extraction' if values['default_mode'] == 'Uttrekk' else 'receipt'
        ))
        # Do not resurrect any previously issued receipt number, LABEL,
        # incoming info.xml, extraction ID or date from a preset.
        self.receipt.clear()
        self.label.clear()
        self.xml.clear()
        self.extraction.clear()
        self.unpack_date.setText(date.today().isoformat())
        self._last_profile_path = Path(filename)
        self.preset_note.setText('Brukerprofil: ' + self._last_profile_path.name)
        self._invalidate()
        try:
            save_config({'last_ingest_user_profile_file': str(self._last_profile_path)})
        except OSError:
            pass

    def _open_preset(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Åpne mottaksprofil', '',
                                                  'JSON (*.json)')
        if not filename:
            return
        try:
            self._apply_preset(filename)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Mottaksprofil', str(error))

    def _preset_values(self):
        return {
            'setup_file': self.setup_file.text().strip(),
            'folder_profile_id': str(self.profile.currentData() or ''),
            'disk': self.disk.text().strip(),
            'group': self.group.text().strip(),
            'owner_code': self.owner.text().strip(),
            'default_mode': 'Uttrekk' if self.mode.currentData() == 'extraction' else 'Mottak',
        }

    def _save_preset(self):
        if self._last_profile_path is None:
            self._save_preset_as()
            return
        answer = QMessageBox.question(
            self, 'Erstatt mottaksprofil?',
            f'Erstatt den eksplisitt valgte profilen?\n{self._last_profile_path}',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._write_preset(self._last_profile_path, replace=True)

    def _save_preset_as(self):
        filename, _ = QFileDialog.getSaveFileName(self, 'Lagre ny mottaksprofil',
                          'mottaksprofil.json', 'JSON (*.json)')
        if filename:
            self._write_preset(Path(filename), replace=False)

    def _write_preset(self, filename, *, replace):
        try:
            from app.ingest_saved_profiles import save_ingest_profile
            saved = save_ingest_profile(filename, self._preset_values(), replace=replace)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Mottaksprofil', str(error))
            return
        self._last_profile_path = saved
        self.preset_note.setText('Brukerprofil: ' + saved.name)
        try:
            save_config({'last_ingest_user_profile_file': str(saved)})
        except OSError:
            pass
