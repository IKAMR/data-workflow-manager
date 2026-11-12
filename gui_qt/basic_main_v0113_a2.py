"""v0.1.13-a2: Basic DIAS metadata UI over the existing common job model.

Advanced and Basic share the same depot_metadata.json, source evidence and
runner. No patching of Qt classes or replacement of result widgets.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QTabWidget, QVBoxLayout, QWidget, QFrame, QGridLayout, QApplication,
)

from app.dias_info_v0113_a2 import (
    DIAS_LINK_LABEL_DELIVERYSPECIFICATION, candidate_info_xml, current_values,
    linked_values, original_evidence_path, persist_metadata, read_original,
)
from noark5_workflow.operations.dias_mets import DIAS_METADATA_FIELDS
from .basic_main_v0113_a1 import DwmMainWindow as _StableBasicWindow


_FIELD_TITLES = {
    'label': 'LABEL',
    'archive_description': 'DELIVERYSPECIFICATION',
    'submission_agreement': 'SUBMISSIONAGREEMENT',
    'delivery_type': 'DELIVERYTYPE',
    'record_status': 'RECORDSTATUS',
    'project_name': 'PROJECTNAME',
    'period_start': 'STARTDATE',
    'period_end': 'ENDDATE',
}


class InfoXmlEditor(QDialog):
    """Edit canonical DIAS fields; show the received XML read-only."""

    def __init__(self, parent, values: dict[str, str], original: Path | None):
        super().__init__(parent)
        self.setWindowTitle('Info.xml – Les / endre DIAS-metadata')
        self.resize(1050, 720)
        self.setMinimumSize(690, 450)
        self.original = original
        self.fields: dict[str, QLineEdit] = {}
        self._syncing = False
        layout = QVBoxLayout(self)
        self.info = QLabel('Original info.xml bevares uendret. Endringene lagres som gjeldende DIAS-metadata i Work.')
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        controls = QHBoxLayout()
        self.path_text = QLabel(str(original) if original else 'Ingen info.xml valgt')
        self.path_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.path_text.setWordWrap(True)
        controls.addWidget(self.path_text, 1)
        choose = QPushButton('Velg original info.xml…')
        choose.clicked.connect(self._choose_original)
        controls.addWidget(choose)
        layout.addLayout(controls)
        tabs = QTabWidget(self)
        layout.addWidget(tabs, 1)
        current_page = QWidget(tabs)
        current_layout = QVBoxLayout(current_page)
        scroll = QScrollArea(current_page)
        scroll.setWidgetResizable(True)
        form_container = QWidget(scroll)
        form = QFormLayout(form_container)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        for key in DIAS_METADATA_FIELDS:
            field = QLineEdit(str(values.get(key) or ''))
            self.fields[key] = field
            form.addRow(_FIELD_TITLES.get(key, key.replace('_', ' ').capitalize()), field)
        scroll.setWidget(form_container)
        current_layout.addWidget(scroll)
        tabs.addTab(current_page, 'Gjeldende (redigerbar)')
        original_page = QWidget(tabs)
        original_layout = QVBoxLayout(original_page)
        self.original_text = QPlainTextEdit(original_page)
        self.original_text.setReadOnly(True)
        original_layout.addWidget(self.original_text)
        tabs.addTab(original_page, 'Original (skrivebeskyttet)')
        if DIAS_LINK_LABEL_DELIVERYSPECIFICATION:
            self.fields['label'].textChanged.connect(
                lambda value: self._link('archive_description', value))
            self.fields['archive_description'].textChanged.connect(
                lambda value: self._link('label', value))
        self._show_original()
        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)

    def _link(self, key: str, value: str):
        if self._syncing:
            return
        self._syncing = True
        try:
            self.fields[key].setText(value)
        finally:
            self._syncing = False

    def _show_original(self):
        self.path_text.setText(str(self.original) if self.original else 'Ingen info.xml valgt')
        if self.original is None:
            self.original_text.setPlainText('Ingen original info.xml er valgt.')
            return
        try:
            if self.original.stat().st_size > 2_000_000:
                self.original_text.setPlainText('Originalen er større enn 2 MB og vises ikke som råtekst.')
            else:
                self.original_text.setPlainText(self.original.read_bytes().decode('utf-8-sig', errors='replace'))
        except (OSError, UnicodeError) as exc:
            self.original_text.setPlainText(f'Kunne ikke vise originalen: {exc}')

    def _choose_original(self):
        initial = str(self.original.parent if self.original else Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, 'Velg original info.xml (DIAS/METS)', initial, 'XML-filer (*.xml);;Alle filer (*)')
        if not path:
            return
        try:
            if Path(path).stat().st_size > 8_000_000:
                raise ValueError('Info.xml er større enn 8 MB.')
            values = read_original(path)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Info.xml', str(exc))
            return
        decision = QMessageBox.question(
            self, 'Importer metadata',
            'Fylle tomme felt fra originalen? Eksisterende redigerte verdier beholdes.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        self.original = Path(path)
        if decision == QMessageBox.StandardButton.Yes:
            for key, field in self.fields.items():
                if not field.text().strip() and values.get(key):
                    field.setText(values[key])
        self._show_original()

    def metadata(self) -> dict[str, str]:
        return linked_values({key: field.text().strip() for key, field in self.fields.items()})


class DwmMainWindow(_StableBasicWindow):
    def __init__(self, *args, **kwargs):
        self._a2_pending_values: dict[str, str] = {}
        self._a2_original: Path | None = None
        self._a2_pending_dirty = False
        super().__init__(*args, **kwargs)
        self._a2_install_metadata_ui()
        self._a2_load_existing_metadata()
        self._a2_install_steps()
        QTimer.singleShot(0, self._a2_fit_initial_window)

    def _a2_install_metadata_ui(self):
        group = next((g for g in self._basic_page.findChildren(QGroupBox)
                      if 'Velg uttrekk' in g.title()), None)
        if group is None:
            raise RuntimeError('Fant ikke Source-panelet i Enkel modus.')
        layout = group.layout()
        row = QHBoxLayout()
        row.addWidget(QLabel('LABEL:'))
        self.basic_dias_label = QLineEdit(group)
        self.basic_dias_label.setPlaceholderText('Beskrivelse / merkelapp for uttrekket')
        self.basic_dias_label.setToolTip('Gjeldende DIAS LABEL. DELIVERYSPECIFICATION følger automatisk.')
        row.addWidget(self.basic_dias_label, 1)
        self.basic_info_xml_button = QPushButton('Info.xml – Les / endre', group)
        self.basic_info_xml_button.clicked.connect(self._a2_edit_info)
        row.addWidget(self.basic_info_xml_button)
        layout.addLayout(row)
        self.basic_dias_note = QLabel('Original info.xml bevares; endringene lagres i Work.')
        self.basic_dias_note.setWordWrap(True)
        layout.addWidget(self.basic_dias_note)
        self.basic_dias_label.editingFinished.connect(self._a2_label_committed)
        self.basic_source_path.textChanged.connect(self._a2_source_changed)

    # The four steps are only views over the established Basic widgets, job
    # list and metadata model.  Never duplicate input fields or runner state.
    def _a2_install_steps(self):
        groups = {group.title()[0]: group for group in
                  self._basic_page.findChildren(QGroupBox)
                  if group.title() and group.title()[0] in '123'}
        if set(groups) != {'1', '2', '3'}:
            raise RuntimeError('Fant ikke de tre opprinnelige Basic-stegene.')
        self._a2_step_groups = {
            'source': groups['1'], 'work': groups['2'], 'run': groups['3'],
        }
        content = groups['1'].parentWidget()
        layout = content.layout()
        navigation = QHBoxLayout()
        navigation.setSpacing(7)
        self._a2_step_buttons = {}
        for key, title in (
            ('overview', 'Oversikt'), ('source', 'Source / metadata'),
            ('work', 'Work'), ('run', 'Kjøring'),
        ):
            button = QPushButton(title, content)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, selected=key:
                                   self._a2_set_step(selected))
            navigation.addWidget(button, 1)
            self._a2_step_buttons[key] = button
        layout.insertLayout(1, navigation)

        # Four short, read-only cards. Values are the actual paths, not
        # truncated folder tails; QLabel supports text selection and wrapping.
        overview = QWidget(content)
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(0, 5, 0, 0)
        overview_layout.setSpacing(9)
        self._a2_overview_labels = {}
        self._a2_overview_statuses = {}
        captions = {
            'joblist': (('Jobbliste', 'Fil'),),
            'source': (('Uttrekksmappe', 'Uttrekk'), ('LABEL', 'LABEL'),
                       ('info.xml (original)', 'Original'), ('info.xml (arbeidskopi)', 'Arbeidskopi')),
            'work': (('Arbeidsmappe', 'Work'),),
            'run': (('Kontrollgrupper', 'Valg'), ('Siste jobbstatus', 'Status')),
        }
        for key, title, action in (
            ('joblist', 'Jobbliste', None),
            ('source', 'Source og DIAS-metadata', 'source'),
            ('work', 'Work', 'work'),
            ('run', 'Kontroller og kjøring', 'run'),
        ):
            card = QFrame(overview)
            card.setObjectName('basic_a2_' + key)
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(13, 10, 13, 10)
            card_layout.setSpacing(12)
            info = QVBoxLayout()
            info.setSpacing(5)
            heading_row = QHBoxLayout()
            heading = QLabel(title, card)
            heading.setStyleSheet('font-weight: 600;')
            heading_row.addWidget(heading)
            status = QLabel('Ikke valgt', card)
            status.setObjectName('basic_a2_status_' + key)
            status.setStyleSheet('font-weight: 600;')
            heading_row.addWidget(status)
            heading_row.addStretch(1)
            self._a2_overview_statuses[key] = status
            info.addLayout(heading_row)
            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(3)
            grid.setColumnMinimumWidth(0, 160)
            grid.setColumnStretch(1, 1)
            for index, (caption, field) in enumerate(captions[key]):
                field_caption = QLabel(caption + ':', card)
                field_caption.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                value = QLabel('Ikke valgt', card)
                value.setWordWrap(True)
                value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                value.setMinimumWidth(0)
                value.setToolTip('Marker teksten for å kopiere den fullstendige stien.')
                grid.addWidget(field_caption, index, 0)
                grid.addWidget(value, index, 1)
                self._a2_overview_labels[field] = value
            info.addLayout(grid)
            card_layout.addLayout(info, 1)
            if key == 'joblist':
                open_button = QPushButton('Åpne…', card)
                open_button.clicked.connect(self._a2_choose_joblist)
                card_layout.addWidget(open_button)
                save_button = QPushButton('Lagre som…', card)
                save_button.clicked.connect(self._a2_save_joblist_as)
                card_layout.addWidget(save_button)
            else:
                button = QPushButton('Se / endre' if key != 'run' else 'Åpne', card)
                button.clicked.connect(lambda _checked=False, selected=action:
                                       self._a2_set_step(selected))
                card_layout.addWidget(button)
            overview_layout.addWidget(card)
        overview_layout.addStretch(1)
        self._a2_overview_start = QPushButton('Start kontroll…', overview)
        self._a2_overview_start.setMinimumHeight(39)
        self._a2_overview_start.clicked.connect(self._start_basic_control)
        overview_layout.addWidget(self._a2_overview_start, 0, Qt.AlignmentFlag.AlignRight)
        layout.insertWidget(2, overview)
        for widget in content.findChildren(QLabel):
            if widget.text() == 'Tre steg for å kontrollere et Noark 5-uttrekk.':
                widget.setText('Jobbliste · Source · Work · Kjøring')
                break
        self._a2_overview_page = overview
        self.basic_dias_label.textChanged.connect(self._a2_refresh_overview)
        self.basic_source_path.textChanged.connect(self._a2_refresh_overview)
        self.basic_work_path.textChanged.connect(self._a2_refresh_overview)
        for check in self.basic_option_checks.values():
            check.toggled.connect(self._a2_refresh_overview)
        self._a2_set_step('overview')

    def _a2_set_step(self, step):
        if not hasattr(self, '_a2_step_buttons') or step not in self._a2_step_buttons:
            return
        self._a2_current_step = step
        self._a2_overview_page.setVisible(step == 'overview')
        for name, group in self._a2_step_groups.items():
            group.setVisible(step == name)
        for name, button in self._a2_step_buttons.items():
            button.setChecked(name == step)
        self._a2_refresh_overview()

    @staticmethod
    def _a2_compact_path(value):
        # Compatibility name from Fix 2: never abbreviate a path in the UI.
        return str(value or '').strip() or 'Ikke valgt'

    def _a2_refresh_overview(self, *_args):
        if not hasattr(self, '_a2_overview_labels'):
            return
        workspace = self.api.workspace()
        joblist = str(workspace.job_list_path or '').strip()
        source = self.basic_source_path.text().strip()
        work = self.basic_work_path.text().strip()
        label = self.basic_dias_label.text().strip()
        original = getattr(self, '_a2_original', None)
        original_path = str(original) if original and Path(original).is_file() else ''
        working_path = ''
        job = self._a2_matching_job() if self._active_id else None
        if job is not None:
            try:
                from noark5_workflow.reporting.depot_metadata import metadata_root_path
                metadata_dir = metadata_root_path(job)
                if metadata_dir is not None:
                    candidate = metadata_dir / 'info-working.xml'
                    if candidate.is_file():
                        working_path = str(candidate)
            except (OSError, ValueError):
                pass
        selected = self._selected_basic_controls()
        values = {
            'Fil': joblist or 'Ingen jobbliste valgt – valgfritt ved kjøring',
            'Uttrekk': self._a2_compact_path(source),
            'LABEL': label or 'Ikke angitt',
            'Original': original_path or 'Ikke funnet / importert',
            'Arbeidskopi': working_path or 'Ikke opprettet',
            'Work': self._a2_compact_path(work),
            'Valg': f'{len(selected)} av 4 valgt',
            'Status': 'Ingen jobb valgt',
        }
        if job is not None:
            try:
                values['Status'] = str(self.api.job_details(self._active_id).job.status)
            except (KeyError, ValueError, RuntimeError, AttributeError):
                pass
        for key, value in values.items():
            widget = self._a2_overview_labels[key]
            if widget.text() != value:
                widget.setText(value)
            widget.setToolTip(value)
        status_values = {
            'joblist': ('Valgt' if joblist else 'Valgfritt'),
            'source': ('Valgt' if source else 'Ikke valgt'),
            'work': ('Valgt' if work else 'Ikke valgt'),
            'run': ('Klar til kjøring' if source and work and selected else 'Mangler valg'),
        }
        for key, value in status_values.items():
            self._a2_overview_statuses[key].setText(value)
        self._a2_overview_start.setEnabled(bool(source and work and selected)
                                            and self._worker is None and not self.api.running)

    def _a2_start_from_overview(self):
        # Opening execution keeps the four control choices visible before run.
        self._a2_set_step('run')

    def _a2_fit_initial_window(self):
        # Advanced already persists geometry in qt/window_geometry. Never
        # override a user's saved window dimensions, even in Basic mode.
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        saved = self.config.value('qt/window_geometry')
        if saved:
            # Keep manually chosen geometry unless it no longer fits on any
            # connected monitor (e.g. when moving from desktop to laptop).
            frame = self.frameGeometry()
            fits = any(frame.intersects(s.availableGeometry())
                       and frame.width() <= s.availableGeometry().width()
                       and frame.height() <= s.availableGeometry().height()
                       for s in QApplication.screens())
            if fits:
                return
        width = min(1450, max(760, area.width() - 70))
        height = min(930, max(540, area.height() - 70))
        width = min(width, area.width())
        height = min(height, area.height())
        self.resize(width, height)
        self.move(area.x() + (area.width() - width) // 2,
                  area.y() + (area.height() - height) // 2)

    def _a2_choose_joblist(self):
        if self._worker is not None or self.api.running:
            QMessageBox.information(self, 'Jobbliste', 'Avslutt kjøringen før jobblisten byttes.')
            return
        current = str(self.api.workspace().job_list_path or '').strip()
        initial = current or str(Path(self.basic_source_path.text()).parent
                                 if self.basic_source_path.text() else Path.home())
        path, _filter = QFileDialog.getOpenFileName(
            self, 'Åpne jobbliste', initial, 'DWM-jobblister (*.n5jobs);;Alle filer (*)')
        if path:
            self._open_path(path)
            self._a2_refresh_overview()

    def _a2_save_joblist_as(self):
        if self._worker is not None or self.api.running:
            QMessageBox.information(self, 'Jobbliste', 'Avslutt kjøringen før jobblisten lagres.')
            return
        # The same Save As command as Advanced; no mandatory new file.
        self._save_as()
        self._a2_refresh_overview()

    def _sync_basic_status(self):
        # The existing 500 ms Basic timer is authoritative for job/run status.
        result = super()._sync_basic_status()
        self._a2_refresh_overview()
        return result

    def _a2_matching_job(self):
        if not self._active_id:
            return None
        try:
            job = self.api._require_job(self._active_id)
        except (AttributeError, KeyError, ValueError):
            return None
        source = getattr(job, 'source_extraction', None)
        if not source or not self.basic_source_path.text():
            return None
        if Path(source).resolve(strict=False) != Path(self.basic_source_path.text()).resolve(strict=False):
            return None
        work = getattr(job, 'work_operations', None)
        selected = self.basic_work_path.text()
        if work and not selected:
            return None
        if work and Path(work).resolve(strict=False) != Path(selected).resolve(strict=False):
            return None
        return job

    def _a2_source_changed(self, source):
        if getattr(self, '_a2_preserve_draft', False):
            return
        if not hasattr(self, 'basic_dias_label'):
            return
        job = self._a2_matching_job()
        if job is not None and not self._a2_pending_dirty:
            self._a2_load_existing_metadata()
            return
        self._a2_pending_values = {}
        self._a2_pending_dirty = bool(source)
        self._a2_original = candidate_info_xml(source) if source and Path(source).is_dir() else None
        if self._a2_original:
            try:
                self._a2_pending_values = read_original(self._a2_original)
            except (ValueError, OSError):
                self._a2_original = None
        label = self._a2_pending_values.get('label') or (Path(source).name if source else '')
        self.basic_dias_label.setText(label)
        self.basic_dias_note.setText(
            ('Fant original: ' + str(self._a2_original)) if self._a2_original else
            'Ingen info.xml funnet automatisk. Bruk Les / endre for å velge fil.')

    def _a2_load_existing_metadata(self):
        if not hasattr(self, 'basic_dias_label') or self._a2_pending_dirty:
            return
        job = self._a2_matching_job()
        if job is None:
            return
        values = current_values(job)
        self._a2_original = original_evidence_path(job) or candidate_info_xml(self.basic_source_path.text())
        self._a2_pending_values = values
        label = values.get('label') or self._a2_pending_values.get('archive_description') or getattr(job, 'name', '')
        self.basic_dias_label.setText(label)
        self.basic_dias_note.setText(
            'Gjeldende DIAS-metadata i Work. ' +
            ('Original: ' + str(self._a2_original) if self._a2_original else 'Ingen importert original.'))

    def _load_basic_active_job(self):
        super()._load_basic_active_job()
        if self._a2_matching_job() is not None and not getattr(self, '_a2_preserve_draft', False):
            self._a2_pending_dirty = False
        self._a2_load_existing_metadata()
        self._a2_refresh_overview()

    def _a2_edit_info(self):
        if self._worker is not None or self.api.running:
            QMessageBox.information(self, 'DIAS-metadata', 'Avslutt kjøringen før metadata redigeres.')
            return
        if not self.basic_source_path.text():
            QMessageBox.information(self, 'DIAS-metadata', 'Velg Source først.')
            return
        job = self._a2_matching_job()
        values = current_values(job) if job and not self._a2_pending_dirty else dict(self._a2_pending_values)
        if self.basic_dias_label.text().strip():
            values = linked_values({**values, 'label': self.basic_dias_label.text().strip()})
        original = self._a2_original
        editor = InfoXmlEditor(self, values, original)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        self._a2_original = editor.original
        self._a2_pending_values = editor.metadata()
        self._a2_pending_dirty = True
        self.basic_dias_label.setText(self._a2_pending_values.get('label', ''))
        if job is not None:
            try:
                self._a2_save_metadata(job)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, 'DIAS-metadata', str(exc))
                return
        else:
            self.basic_dias_note.setText('Metadata klargjort. Lagres i valgt Work når jobben opprettes.')

    def _a2_label_committed(self):
        value = self.basic_dias_label.text().strip()
        if not value:
            QMessageBox.warning(self, 'LABEL', 'LABEL kan ikke være tom.')
            return
        self._a2_pending_values = linked_values({**self._a2_pending_values, 'label': value})
        self._a2_pending_dirty = True
        job = self._a2_matching_job()
        if job is not None and self._worker is None and not self.api.running:
            try:
                self._a2_save_metadata(job)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, 'DIAS-metadata', str(exc))

    def _a2_save_metadata(self, job):
        if not self._a2_pending_dirty:
            return
        values = linked_values({**self._a2_pending_values, 'label': self.basic_dias_label.text().strip()})
        # If the original is already a preserved Work copy, do not reimport it
        # as a different source; the source evidence is already recorded.
        already = original_evidence_path(job)
        original = self._a2_original
        if original and already and original.resolve(strict=False) == already.resolve(strict=False):
            original = None
        json_path, xml_path = persist_metadata(job, values, original)
        self._a2_pending_values = current_values(job)
        self._a2_pending_dirty = False
        self.basic_dias_note.setText(f'Lagret i Work: {json_path.name} og {xml_path.name}')

    def _start_basic_control(self):
        self._a2_set_step('run')
        # The original Basic flow refreshes the job list after creating a job.
        # Do not discard pre-run DIAS edits during that refresh.
        self._a2_preserve_draft = True
        try:
            return super()._start_basic_control()
        finally:
            self._a2_preserve_draft = False

    def _run_selected(self):
        # Basic and Advanced keep exactly the same worker path. Only persist
        # pending metadata before the shared runner is invoked.
        if getattr(self, '_basic_active', False) and self._a2_pending_dirty:
            job = self._a2_matching_job()
            if job is None:
                QMessageBox.warning(self, 'DIAS-metadata', 'Kan ikke knytte DIAS-metadata til valgt jobb.')
                return
            try:
                self._a2_save_metadata(job)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, 'DIAS-metadata', str(exc))
                return
        return super()._run_selected()

    def _continue_job(self):
        if getattr(self, '_basic_active', False) and self._a2_pending_dirty:
            job = self._a2_matching_job()
            if job is None:
                QMessageBox.warning(self, 'DIAS-metadata', 'Kan ikke knytte DIAS-metadata til valgt jobb.')
                return
            try:
                self._a2_save_metadata(job)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, 'DIAS-metadata', str(exc))
                return
        return super()._continue_job()
