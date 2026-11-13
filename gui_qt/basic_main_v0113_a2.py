"""v0.1.13-a2: Basic DIAS metadata UI over the existing common job model.

Advanced and Basic share the same depot_metadata.json, source evidence and
runner. No patching of Qt classes or replacement of result widgets.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QTabWidget, QVBoxLayout, QWidget, QFrame, QGridLayout, QApplication,
)

from app.dias_status_v0113_a3 import describe_info_xml_status
from app.dias_info_v0113_a2 import (
    DIAS_LINK_LABEL_DELIVERYSPECIFICATION, candidate_info_xml, current_values,
    linked_values, original_evidence_path, persist_metadata, read_original,
)
from noark5_workflow.operations.dias_mets import DIAS_METADATA_FIELDS
from app.basic_drop_v0113_a3 import classify_basic_drop
from app.basic_work_guard_v0113_a3 import inspect_work, nearby_job_lists, _same, work_contains_only_joblists
from app.basic_joblist_suggestion_v0113_a3 import suggest_joblist_path
from .basic_main_v0113_a1 import DwmMainWindow as _StableBasicWindow
from .window_positions_v0114_a1 import install_window_positions
from .console_alert_v0114_a1 import install_console_alert
from .result_label_width_v0114_a1 import constrain_detail_label_width


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
            self, 'Velg original info.xml (DIAS/METS)', initial, 'XML-filer (*.xml);;Alle filer (*)',
            options=QFileDialog.Option.DontUseNativeDialog)
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
        self._a2_original_fields: dict[str, str] = {}
        self._a2_pending_dirty = False
        self._a3_manually_loaded_info = False
        self._a3_work_approval = None
        self._a3_autorun_armed = False
        self._a3_auto_results_pending = False
        super().__init__(*args, **kwargs)
        self._a2_install_metadata_ui()
        self._a2_load_existing_metadata()
        self._a2_install_steps()
        self._a14_console_alert = install_console_alert(self, self._a2_navigation)
        self._a3_install_new_control()
        self._a3_install_auto_views()
        self._a3_install_run_joblist()
        self._a3_simplify_run_text()
        self._a3_enable_drops()
        QTimer.singleShot(0, self._a2_fit_initial_window)
        # Version-independent QSettings geometry and popup positions follow
        # the main window even with a laptop + ultrawide monitor setup.
        self._a14_window_positions = install_window_positions(self)
        QTimer.singleShot(0, self._a14_open_completed_job_in_run)

    def _a14_open_completed_job_in_run(self):
        """A saved, completed job should open on its results/run step."""
        if not getattr(self, '_basic_active', False) or not getattr(self, '_active_id', None):
            return
        try:
            status = str(self.api.job_details(self._active_id).job.status).strip().casefold()
        except (AttributeError, KeyError, ValueError, RuntimeError):
            return
        if status in {'ferdig', 'fullført', 'fullfort', 'completed'}:
            self._a2_set_step('run')

    def _a12_open_result_center(self, *args, **kwargs):
        """Retain result-window size, position and maximized state across restarts."""
        before = tuple(getattr(self, '_a12_result_windows', ()))
        result = super()._a12_open_result_center(*args, **kwargs)
        controller = getattr(self, '_a14_window_positions', None)
        if controller is not None:
            for viewer in getattr(self, '_a12_result_windows', ()):
                if viewer not in before:
                    controller.register_result_window(viewer)
                    self._a14_limit_result_label_columns(viewer)
                    from .standard_values_v0114_a2 import install_standard_values_link
                    install_standard_values_link(viewer)
        return result

    def _a14_limit_result_label_columns(self, viewer):
        """Keep evidence labels bounded, even when Resultatvisninger is maximized.

        The established viewer still controls content and evidence selection;
        this only adjusts its presentation after each selection change.
        """
        from types import MethodType
        original = viewer._show_detail

        def constrain_current():
            for browser in getattr(viewer, '_a53_browsers', {}).values():
                # Only the active detail tab is updated by the viewer. Rewriting
                # an unchanged HTML document would disturb scroll position.
                html = browser.toHtml()
                adjusted = constrain_detail_label_width(html)
                if adjusted != html:
                    browser.setHtml(adjusted)

        def show_detail(instance, tab):
            result = original(tab)
            browser = getattr(instance, '_a53_browsers', {}).get(tab)
            if browser is not None:
                html = browser.toHtml()
                adjusted = constrain_detail_label_width(html)
                if adjusted != html:
                    browser.setHtml(adjusted)
            return result

        viewer._show_detail = MethodType(show_detail, viewer)
        constrain_current()

    def _a3_place_dialog(self, dialog, kind: str) -> None:
        """v0.1.14-a1: stay on the screen containing this DWM window."""
        controller = getattr(self, '_a14_window_positions', None)
        if controller is None:
            return super()._a3_place_dialog(dialog, kind)
        controller._place(dialog)

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
            button = QPushButton('Source' if key == 'source' else title, content)
            button.setCheckable(True)
            button.setMinimumHeight(40)
            # Only the active page has the accent; other tabs keep app styling.
            button.setStyleSheet(
                'QPushButton:checked {'
                ' background-color: #307e60; color: white;'
                ' border: 2px solid #8dd7ad; font-weight: 700;'
                '}'
            )
            button.clicked.connect(lambda _checked=False, selected=key:
                                   self._a2_set_step(selected))
            navigation.addWidget(button, 1)
            self._a2_step_buttons[key] = button
        # Previous/Next belong to the same row as the stage tabs, so navigation
        # remains visible without scrolling to the bottom of the form.
        navigation.addSpacing(8)
        self._a3_previous_button = QPushButton('← Forrige', content)
        self._a3_previous_button.setToolTip('Gå til forrige steg')
        self._a3_previous_button.clicked.connect(lambda: self._a3_move_step(-1))
        navigation.addWidget(self._a3_previous_button)
        self._a3_next_button = QPushButton('Neste →', content)
        self._a3_next_button.setToolTip('Gå til neste steg')
        self._a3_next_button.clicked.connect(lambda: self._a3_move_step(1))
        navigation.addWidget(self._a3_next_button)
        layout.insertLayout(1, navigation)
        self._a2_navigation = navigation

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
                       ('info.xml', 'InfoStatus')),
            'work': (('Arbeidsmappe', 'Work'),),
            'run': (('Kontrollgrupper', 'Valg'), ('Siste jobbstatus', 'Status')),
        }
        for key, title, action in (
            ('source', '1. Source og DIAS-metadata', 'source'),
            ('work', '2. Work', 'work'),
            ('run', '3. Kontroller og kjøring', 'run'),
            ('joblist', 'Jobbliste (valgfritt)', None),
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
                widget.setText('Source og info.xml · Work · Kjøring · Jobbliste (valgfritt)')
                break
        self._a2_overview_page = overview
        self.basic_dias_label.textChanged.connect(self._a2_refresh_overview)
        self.basic_source_path.textChanged.connect(self._a2_refresh_overview)
        self.basic_work_path.textChanged.connect(self._a2_refresh_overview)
        for check in self.basic_option_checks.values():
            check.toggled.connect(self._a2_refresh_overview)
        self._a2_set_step('overview')

    def _a3_install_run_joblist(self):
        """Show the shared, optional job list where the run is configured.

        These controls use the existing Basic/Advanced open and save methods;
        they do not create a second job-list state or require saving to run.
        """
        group = self._a2_step_groups['run']
        layout = group.layout()
        row = QHBoxLayout()
        caption = QLabel('Jobbliste (valgfritt):', group)
        row.addWidget(caption)
        self._a3_run_joblist_path = QLabel('Ikke lagret', group)
        self._a3_run_joblist_path.setObjectName('basic_a3_run_joblist_path')
        self._a3_run_joblist_path.setWordWrap(True)
        self._a3_run_joblist_path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._a3_run_joblist_path.setMinimumWidth(0)
        row.addWidget(self._a3_run_joblist_path, 1)
        self._a3_run_open_joblist = QPushButton('Åpne…', group)
        self._a3_run_open_joblist.clicked.connect(self._a2_choose_joblist)
        row.addWidget(self._a3_run_open_joblist)
        self._a3_run_save_joblist = QPushButton('Lagre som…', group)
        self._a3_run_save_joblist.clicked.connect(self._a2_save_joblist_as)
        row.addWidget(self._a3_run_save_joblist)
        layout.insertLayout(0, row)
        self._a2_refresh_overview()

    def _a3_simplify_run_text(self):
        """Keep Basic run controls useful without repeating Setup documentation."""
        # The existing Basic class updates this label when controls change.
        # Preserve its underlying state, but do not display the long paragraph.
        self.basic_workflow_description.hide()
        group = self._a2_step_groups['run']
        for note in group.findChildren(QLabel):
            if note.text().startswith('Før første kjøring vil DWM'):
                note.setText('Fullført kontroll betyr ikke faglig godkjent uttrekk.')
                break

    def _a3_install_new_control(self):
        """New Basic run uses the same empty workspace as Advanced / Ny jobbliste."""
        content = self.basic_advanced_button.parentWidget()
        header = content.layout().itemAt(0).layout()
        self.basic_new_control_button = QPushButton('Ny kontroll', content)
        self.basic_new_control_button.setToolTip(
            'Starter med tom Source, Work og jobbliste. Tidligere filer og resultater bevares.')
        self.basic_new_control_button.clicked.connect(self._a3_new_control)
        header.insertWidget(header.indexOf(self.basic_advanced_button),
                            self.basic_new_control_button, 0, Qt.AlignmentFlag.AlignTop)

        # Importing info.xml may precede the Source folder. Store metadata as a
        # draft until the same shared job is created; no files are written to Source.
        source_group = self._a2_step_groups['source']
        source_layout = source_group.layout()
        # The LABEL-adjacent "Info.xml – Les / endre" button handles both
        # importing an original and editing the shared DIAS metadata.
        # Avoid a duplicate button at the top of Source.
        # One instruction only: both entry orders are valid.
        for note in source_group.findChildren(QLabel):
            if 'Velg mappen som inneholder selve Noark 5-uttrekket' in note.text():
                note.setText('Velg uttrekksmappe eller les info.xml. Rekkefølgen er valgfri.')
                break

    def _a3_new_control(self):
        """Reset open joblist, too. Do not discard unsaved changes silently."""
        if self._worker is not None or self.api.running:
            QMessageBox.information(self, 'Ny kontroll',
                'Avslutt pågående kjøring før du starter en ny kontroll.')
            return
        if not self._maybe_save():
            return
        try:
            # Identical state transition to Advanced / Ny jobbliste.
            self.api.new_job_list()
        except Exception as exc:
            self._error(exc)
            return
        self._active_id = None
        self._render_key = None
        self._a8_run_context = None
        self._a8_live_job = None
        self.config.setValue('qt/skip_auto_reopen', True)
        self.config.setValue('qt/last_job_list', '')
        self._refresh_recent_menu()
        self._a2_pending_values = {}
        self._a2_original = None
        self._a2_original_fields = {}
        self._a2_pending_dirty = False
        self._a3_manually_loaded_info = False
        self._a3_work_approval = None
        self._a3_auto_results_pending = False
        self._reset_basic_selection()
        self.basic_dias_label.clear()
        self.basic_dias_note.setText('Ingen info.xml funnet eller valgt.')
        self._refresh(force=True)
        self._a2_set_step('overview')

    def _a3_load_info_xml(self):
        """The dedicated button loads original METS before Source or Work exists."""
        if self._worker is not None or self.api.running:
            QMessageBox.information(self, 'Info.xml',
                'Avslutt pågående kjøring før metadata leses.')
            return
        source = self.basic_source_path.text().strip()
        initial = str(Path(source) if source else
                      self._a2_original.parent if self._a2_original else Path.home())
        selected, _ = QFileDialog.getOpenFileName(
            self, 'Les original info.xml', initial,
            'XML-filer (*.xml);;Alle filer (*)',
            options=QFileDialog.Option.DontUseNativeDialog)
        if selected:
            self._a3_import_info_path(selected)

    def _a3_import_info_path(self, selected):
        """Import as a pending draft; original bytes are copied to Work on save."""
        if self._worker is not None or self.api.running:
            return False
        try:
            path = Path(selected)
            if not path.is_file() or path.stat().st_size > 8_000_000:
                raise ValueError('info.xml mangler eller er større enn 8 MB.')
            values = read_original(path)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Info.xml', str(exc))
            return False
        existing = dict(self._a2_pending_values)
        existing.update({key: value for key, value in values.items() if value})
        self._a2_pending_values = existing
        self._a2_original = path
        self._a2_original_fields = dict(values)
        self._a2_pending_dirty = True
        self._a3_manually_loaded_info = True
        self.basic_dias_label.setText(str(values.get('label') or existing.get('label') or ''))
        self.basic_dias_note.setText('Info.xml valgt: ' + str(path))
        self._a2_set_step('source')
        return True

    def _a3_enable_drops(self):
        """Attach local-file drops to the existing widgets, not a second GUI."""
        self._a3_drop_targets = {}
        targets = [
            (self._a2_step_groups['source'], 'source'),
            (self._a2_step_groups['work'], 'work'),
            (self._a2_overview_page.findChild(QFrame, 'basic_a2_source'), 'source'),
            (self._a2_overview_page.findChild(QFrame, 'basic_a2_work'), 'work'),
            (self._a2_overview_page.findChild(QFrame, 'basic_a2_joblist'), 'joblist'),
        ]
        for root_widget, role in targets:
            if root_widget is None:
                continue
            # All visible labels, path fields and card backgrounds are targets.
            for widget in (root_widget, *root_widget.findChildren(QWidget)):
                if widget is self.basic_dias_label:
                    continue  # LABEL stays a normal editable text field.
                self._a3_drop_targets[widget] = role
                widget.setAcceptDrops(True)
                widget.installEventFilter(self)
        # The single Info.xml button also accepts direct XML drops.
        widget = self.basic_info_xml_button
        self._a3_drop_targets[widget] = 'info'
        widget.setAcceptDrops(True)
        widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        role = getattr(self, '_a3_drop_targets', {}).get(watched)
        if role and event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
            if len(urls) != 1 or not urls[0].isLocalFile():
                event.ignore()
                return True
            try:
                action, path = classify_basic_drop(urls[0].toLocalFile(), role)
            except ValueError:
                event.ignore()
                return True
            if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                event.acceptProposedAction()
                return True
            event.acceptProposedAction()
            self._a3_handle_drop(action, path)
            return True
        return super().eventFilter(watched, event)

    def _a3_handle_drop(self, action, path):
        if self._worker is not None or self.api.running:
            QMessageBox.information(self, 'Dra og slipp',
                                    'Avslutt kjøringen før du endrer mapper eller metadata.')
            return
        if action == 'info':
            self._a3_import_info_path(path)
        elif action == 'source':
            self._a3_accept_source(path)
        elif action == 'work':
            self._a3_accept_work(path)
        elif action == 'joblist':
            if self._maybe_save():
                self._open_path(str(path))
                self._a2_refresh_overview()

    def _a3_accept_source(self, folder):
        """Same validation and state transitions as ordinary Finn uttrekk."""
        from app.job_preflight_v018_a6 import check_extraction_folder
        from app.storage_profiles_v0110_a1 import suggest_known_source_work
        from app.storage_profiles_v0110_a2 import resolve_storage_profile
        source = str(folder)
        try:
            issues = check_extraction_folder(source, profile_id='noark5')
        except Exception as exc:
            QMessageBox.warning(self, 'Kunne ikke lese uttrekket', str(exc))
            return
        if issues:
            QMessageBox.warning(self, 'Dette er ikke en Noark 5-uttrekksmappe',
                                '\n\n'.join(issue.message for issue in issues))
            return
        old_source = self.basic_source_path.text().strip()
        if old_source and Path(old_source).resolve(strict=False) != folder.resolve(strict=False):
            self._a3_manually_loaded_info = False
            self._a2_original = None
            self._a2_original_fields = {}
            self._a2_pending_values = {}
            self._a2_pending_dirty = False
        self.config.setValue('qt/last_new_source_dir', source)
        self.basic_source_path.setText(source)
        self.basic_work_path.clear()
        self._a3_work_approval = None
        self._basic_job_id = None
        self._basic_legacy_layout = False
        self._basic_selection_edited = True
        self.basic_choose_work.setEnabled(True)
        self.basic_source_hint.setText('Noark 5-uttrekksmappe gjenkjent.')
        self.basic_work_hint.setText('Velg en tom Work-mappe. Valgt mappe brukes direkte.')
        try:
            profile = resolve_storage_profile(self.api.settings)
            roles = suggest_known_source_work(source, profile_id=profile)
            if roles.get('work_root'):
                self.basic_work_hint.setText(
                    'Mulig plassering: ' + str(roles['work_root']) +
                    '. Basic bruker mappen du velger direkte.')
        except (ValueError, OSError):
            pass
        self._sync_basic_status()
        self._a2_set_step('source')

    def _choose_basic_work(self):
        """Apply the same guarded selection to the picker and drag-and-drop."""
        if not self.basic_source_path.text() or self._worker is not None or self.api.running:
            return
        source = Path(self.basic_source_path.text())
        current = self.basic_work_path.text().strip()
        initial = current or str(source.parent)
        folder = QFileDialog.getExistingDirectory(
            self, 'Velg Work-mappe', initial,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog)
        if folder:
            self._a3_accept_work(Path(folder))

    def _a3_accept_work(self, folder):
        """Inspect Work, show contents, then request explicit permission."""
        from app.basic_start_v0111_a1 import prepare_basic_plan, existing_basic_job
        source = self.basic_source_path.text().strip()
        if not source:
            QMessageBox.information(self, 'Work', 'Velg Source før Work.')
            return
        try:
            plan = prepare_basic_plan(source, str(folder), self.api.settings,
                                      controls=self._selected_basic_controls())
            inspection = inspect_work(plan.work_operations, plan.source_extraction)
            match = existing_basic_job(self.api, plan)
            kind = ('same_job' if inspection.kind == 'unknown_job' and match is not None
                    else inspection.kind)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Ugyldig Work-plassering', str(exc))
            return
        if kind == 'different_source':
            QMessageBox.warning(self, 'Work: feil Source',
                'Registrert Source er forskjellig fra valgt uttrekk. '
                'Denne Work-mappen kan ikke brukes. Ingen filer endres.\n\n'
                + inspection.summary())
            return
        if kind == 'unknown_job':
            self._a3_offer_existing_work(
                plan, inspection, unknown_source=True)
            return
        if kind == 'same_job' and match is None:
            self._a3_offer_existing_work(
                plan, inspection, unknown_source=False)
            return
        if kind != 'empty':
            answer = QMessageBox.question(
                self, 'Work inneholder allerede data',
                'Bekrefter du at denne mappen skal brukes til kontrollen?\n'
                'DWM flytter eller sletter ikke eksisterende filer.\n\n'
                + inspection.summary(),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._a3_work_approval = (str(plan.source_extraction.resolve(strict=False)),
                                  str(plan.work_operations.resolve(strict=False)),
                                  kind)
        self.config.setValue('qt/last_work_dir', str(folder))
        self.basic_work_path.setText(str(folder))
        self._basic_job_id = None
        self._basic_legacy_layout = False
        self._basic_selection_edited = True
        self.basic_work_hint.setText('Work valgt: ' + str(plan.work_operations) +
                                     (' (eksisterende innhold godkjent)' if inspection.count else ' (tom mappe)'))
        self._sync_basic_status()
        self._a2_set_step('work')

    def _a3_offer_existing_work(self, plan, inspection, *, unknown_source: bool):
        """Offer recovery through the *shared* job-list API, never adopt raw Work.

        A folder name or adjacent .n5jobs file is not proof of identity.
        The opened job must independently match both source and Work path.
        Existing controls and results are not rewritten or restarted.
        """
        if self._worker is not None or self.api.running:
            return
        candidates = nearby_job_lists(plan.work_operations)
        caption = ('Source kan ikke bekreftes fra denne Work-mappen.'
                   if unknown_source else
                   'Source stemmer, men jobben er ikke åpnet i gjeldende jobbliste '
                   'med samme kontrolloppsett.')
        if candidates:
            nearby = '\n'.join('  - ' + str(item) for item in candidates[:8])
            caption += ('\n\nMulige jobblister i nærheten (ikke verifisert):\n'
                        + nearby)
        message = QMessageBox(self)
        message.setWindowTitle('Eksisterende Work – åpne riktig jobb')
        message.setIcon(QMessageBox.Icon.Warning)
        message.setText(caption)
        message.setInformativeText(
            'Åpne eksisterende .n5jobs for å kontrollere jobbidentiteten. '
            'Ingen Work-filer slettes eller overskrives.\n\n'
            + inspection.summary())
        open_button = message.addButton('Åpne jobbliste…', QMessageBox.ButtonRole.AcceptRole)
        message.addButton('Velg annen Work', QMessageBox.ButtonRole.RejectRole)
        message.exec()
        if message.clickedButton() is not open_button:
            return
        if not self._maybe_save():
            return
        start_dir = str(candidates[0].parent) if candidates else str(plan.work_operations)
        filename, _ = QFileDialog.getOpenFileName(
            self, 'Åpne eksisterende DWM-jobbliste', start_dir,
            'DWM-jobblister (*.n5jobs)',
            options=QFileDialog.Option.DontUseNativeDialog)
        if not filename:
            return
        # The regular open path validates the file and handles all shared state.
        self._open_path(filename)
        workspace = self.api.workspace()
        if not workspace.job_list_path or not _same(workspace.job_list_path, filename):
            return
        found = None
        for view in workspace.jobs:
            try:
                job = self.api.job_details(view.job_id).job
                job_source = getattr(job, 'source_extraction', None)
                job_work = getattr(job, 'effective_work_operations', None)
                if (job_source and job_work and
                        _same(job_source, plan.source_extraction) and
                        _same(job_work, plan.work_operations)):
                    found = view.job_id
                    break
            except (ValueError, OSError, AttributeError):
                continue
        if found is None:
            QMessageBox.warning(
                self, 'Jobblisten samsvarer ikke',
                'Den åpnede jobblisten har ingen jobb med både valgt Source '
                'og nøyaktig denne Work-mappen. Work er ikke godkjent. '
                'Velg riktig jobbliste eller en ny Work-mappe.')
            return
        self.api.select_job(found)
        self._active_id = found
        self._basic_job_id = found
        self._a3_work_approval = None
        self._load_basic_active_job()
        self._refresh(force=True)
        self._a2_set_step('work')
        QMessageBox.information(
            self, 'Eksisterende jobb åpnet',
            'Source og Work er bekreftet mot den åpne jobblisten. '
            'Eksisterende kontrolloppsett og resultater er beholdt. '
            'Kontroller valgte operasjoner før ny kjøring.')

    def _a3_install_auto_views(self):
        """Vis to tydelige grupper uten å endre kontroller eller kjøringslogikk."""
        group = self._a2_step_groups['run']
        layout = group.layout()
        # Bruk den eksisterende overskriften over kontrollvalgene.
        for label in group.findChildren(QLabel):
            if label.text().strip() == 'Velg kontroller:':
                label.setText('Kontroller som skal kjøres')
                break
        self._a3_auto_results = QCheckBox('Åpne Resultatvisninger etter kjøring', group)
        self._a3_auto_details = QCheckBox('Åpne Kjøredetaljer ved start', group)
        self._a3_auto_log = QCheckBox('Åpne kjørelogg ved start', group)
        for key, widget, default in (
            ('results', self._a3_auto_results, True),
            ('details', self._a3_auto_details, False),
            ('log', self._a3_auto_log, False),
        ):
            widget.setChecked(self.config.value('qt/a3_basic_auto_' + key, default, type=bool))
            widget.toggled.connect(lambda checked, name=key:
                                   self.config.setValue('qt/a3_basic_auto_' + name, checked))
        anchor = layout.indexOf(self.basic_workflow_description)
        self._a3_auto_views_heading = QLabel('Automatisk åpning av vinduer', group)
        self._a3_auto_views_heading.setContentsMargins(0, 10, 0, 2)
        layout.insertWidget(anchor + 1, self._a3_auto_views_heading)
        for offset, widget in enumerate((self._a3_auto_results,
                                          self._a3_auto_details, self._a3_auto_log), 2):
            layout.insertWidget(anchor + offset, widget)

    def _a3_create_approved_job(self, plan):
        """Use the shared API to create a job in explicitly approved, non-DWM Work."""
        from app.basic_start_v0111_a1 import existing_basic_job
        previous = existing_basic_job(self.api, plan)
        if previous is not None:
            self.api.select_job(previous)
            return previous, False
        inspection = inspect_work(plan.work_operations, plan.source_extraction)
        list_only = (inspection.kind == 'empty' and inspection.count > 0
                     and work_contains_only_joblists(plan.work_operations))
        if inspection.kind != 'unrelated' and not list_only:
            raise ValueError('Work er ikke lenger en godkjent mappe uten DWM-jobbdata.')
        token = getattr(self, '_a3_work_approval', None)
        if (token is None or not _same(token[0], plan.source_extraction)
                or not _same(token[1], plan.work_operations)
                or token[2] not in ('unrelated', 'empty')):
            raise ValueError('Work med innhold må først godkjennes i Work-steget.')
        view = self.api.create_job(source_extraction=str(plan.source_extraction),
                                   name=plan.source_extraction.name, profile_id='noark5')
        try:
            self.api.update_storage(view.job_id, {
                'work_root': str(plan.work_root),
                'work_operations': str(plan.work_operations),
            })
            self.api.set_workflow(view.job_id, plan.operation_ids)
            self.api.use_selected_work_directly(view.job_id)
        except Exception:
            try:
                self.api.remove_job(view.job_id)
            except Exception:
                pass
            raise
        return view.job_id, True

    def _a3_auto_start_windows(self):
        if not getattr(self, '_a3_autorun_armed', False):
            return
        self._a3_autorun_armed = False
        if self._a3_auto_details.isChecked():
            self._open_basic_run_details()
        if self._a3_auto_log.isChecked():
            self._a8_show_job_log()

    @staticmethod
    def _a3_neighbor_step(step, direction):
        steps = ('overview', 'source', 'work', 'run')
        if step not in steps or direction not in (-1, 1):
            return None
        next_index = steps.index(step) + direction
        return steps[next_index] if 0 <= next_index < len(steps) else None

    def _a3_move_step(self, direction):
        target = self._a3_neighbor_step(self._a2_current_step, direction)
        if target is not None:
            self._a2_set_step(target)

    def _a2_set_step(self, step):
        if not hasattr(self, '_a2_step_buttons') or step not in self._a2_step_buttons:
            return
        self._a2_current_step = step
        self._a2_overview_page.setVisible(step == 'overview')
        for name, group in self._a2_step_groups.items():
            group.setVisible(step == name)
        for name, button in self._a2_step_buttons.items():
            button.setChecked(name == step)
        # Qt-free view contracts and early initialization can call this method
        # before the optional navigation controls have been created.
        if hasattr(self, '_a3_previous_button') and hasattr(self, '_a3_next_button'):
            self._a3_previous_button.setEnabled(self._a3_neighbor_step(step, -1) is not None)
            self._a3_next_button.setEnabled(self._a3_neighbor_step(step, 1) is not None)
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
        # The Kjøring page and Oversikt must always show the same live job-list
        # selection, including after New Control, Open, Save As and auto-save.
        if hasattr(self, '_a3_run_joblist_path'):
            display = joblist or 'Ikke lagret'
            self._a3_run_joblist_path.setText(display)
            self._a3_run_joblist_path.setToolTip(display)
            idle = self._worker is None and not self.api.running
            self._a3_run_open_joblist.setEnabled(idle)
            self._a3_run_save_joblist.setEnabled(idle)
        source = self.basic_source_path.text().strip()
        work = self.basic_work_path.text().strip()
        label = self.basic_dias_label.text().strip()
        job = self._a2_matching_job() if self._active_id else None
        current = {}
        imports = ()
        if job is not None:
            from noark5_workflow.reporting.depot_metadata import load_depot_metadata
            stored = load_depot_metadata(job)
            current = dict(stored.get('current') or {})
            imports = tuple(stored.get('source_imports') or ())
        if self._a2_pending_dirty:
            current = dict(self._a2_pending_values)
            if label != str(current.get('label') or '').strip():
                current['label'] = label
                if DIAS_LINK_LABEL_DELIVERYSPECIFICATION:
                    current['archive_description'] = label
        info_status = describe_info_xml_status(
            current, imports, original=self._a2_original,
            original_fields=getattr(self, '_a2_original_fields', {}),
            dirty=bool(self._a2_pending_dirty),
        )
        selected = self._selected_basic_controls()
        values = {
            'Fil': joblist or 'Ikke lagret',
            'Uttrekk': self._a2_compact_path(source),
            'LABEL': label or 'Ikke angitt',
            'InfoStatus': info_status,
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
            'joblist': ('Valgt' if joblist else 'Ikke lagret'),
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
        # Restore the last user-selected screen and position across versions.
        # Never center/resize on launch when a usable geometry is already saved.
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        if self.config.value('qt/window_geometry'):
            # The Qt restore path in main_window.py owns saved geometry.
            # Disconnected screens are corrected by the a14 position controller.
            return
        area = screen.availableGeometry()
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
            self, 'Åpne jobbliste', initial, 'DWM-jobblister (*.n5jobs);;Alle filer (*)',
            options=QFileDialog.Option.DontUseNativeDialog)
        if path:
            self._open_path(path)
            self._a2_refresh_overview()

    def _save_as(self) -> bool:
        """Suggest a job-list location for Basic; retain Advanced's Save As."""
        if not getattr(self, '_basic_active', False):
            return super()._save_as()
        workspace = self.api.workspace()
        existing = str(workspace.job_list_path or '').strip()
        if existing:
            initial = existing
        else:
            proposal = suggest_joblist_path(
                source=self.basic_source_path.text().strip(),
                work=self.basic_work_path.text().strip(),
                label=self.basic_dias_label.text().strip(),
                settings=self.api.settings,
            )
            initial = str(proposal) if proposal else str(
                self.config.value('qt/last_job_list', '') or Path.home())
        # Windows native Save As falls back to the process CWD when the proposed
        # directory does not exist. Create ONLY the proposed leaf directory for
        # the dialog, and remove it on cancel if still empty. A confirmed save
        # retains it; never touch an existing directory or files.
        proposed_dir = Path(initial).parent
        temporary_suggestion_dir = False
        if (not existing and proposal is not None
                and proposed_dir == proposal.parent
                and proposed_dir.parent.is_dir() and not proposed_dir.exists()):
            try:
                proposed_dir.mkdir()
                temporary_suggestion_dir = True
            except OSError:
                pass  # A platform-specific dialog can still be used manually.
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, 'Lagre jobbliste som', initial, 'DWM-jobbliste (*.n5jobs)',
                options=QFileDialog.Option.DontUseNativeDialog)
        except BaseException:
            if temporary_suggestion_dir:
                try:
                    proposed_dir.rmdir()
                except OSError:
                    pass
            raise
        if not filename:
            if temporary_suggestion_dir:
                try:
                    proposed_dir.rmdir()  # Only succeeds while empty.
                except OSError:
                    pass
            return False
        if temporary_suggestion_dir and Path(filename).parent != proposed_dir:
            try:
                proposed_dir.rmdir()  # User chose another location.
            except OSError:
                pass
        target = Path(filename)
        if target.suffix.casefold() != '.n5jobs':
            target = target.with_suffix('.n5jobs')
        try:
            # Persist the selected path only after explicit confirmation.
            target.parent.mkdir(parents=True, exist_ok=True)
            output = self.api.save_job_list(target)
        except (OSError, ValueError, RuntimeError) as exc:
            self._error(exc)
            return False
        self._remember_joblist(str(output))
        self._refresh(force=True)
        return True

    def _start_worker(self, jobs, *, request_id=None):
        """Basic: a job list is optional; Advanced keeps mandatory save."""
        if not getattr(self, '_basic_active', False):
            return super()._start_worker(jobs, request_id=request_id)
        self._a3_run_without_joblist = False
        if not self.api.workspace().job_list_path:
            decision = QMessageBox.question(
                self, 'Lagre jobbliste?',
                'Vil du lagre jobblisten før kontrollen starter?\n\n'
                'Ja: Velg fil og lagre.\n'
                'Nei: Kjør uten jobblistefil; Work-resultatene lagres likevel.\n'
                'Avbryt: Ikke start kontrollen.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if decision == QMessageBox.StandardButton.Cancel:
                return
            if decision == QMessageBox.StandardButton.Yes:
                if not self._save_as():
                    return
            elif decision == QMessageBox.StandardButton.No:
                self._a3_run_without_joblist = True
            else:
                return
        try:
            return super()._start_worker(jobs, request_id=request_id)
        finally:
            self._a3_run_without_joblist = False

    def _save(self) -> bool:
        # Shared runner invokes _save() even when no list path exists. The
        # operator explicitly chose to run unsaved, so bypass ONLY this one
        # mandatory-save checkpoint in Basic; leave Advanced untouched.
        if (getattr(self, '_basic_active', False)
                and getattr(self, '_a3_run_without_joblist', False)
                and not self.api.workspace().job_list_path):
            return True
        return super()._save()

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
        if (getattr(self, '_a3_auto_results_pending', False)
                and self._worker is None and not self.api.running and self._active_id):
            try:
                status = self.api.job_details(self._active_id).job.status
            except Exception:
                status = ''
            if status in ('Ferdig', 'Feil', 'Hoppet over'):
                self._a3_auto_results_pending = False
                QTimer.singleShot(0, self._open_basic_results)
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
        if getattr(self, '_a3_manually_loaded_info', False) and self._a2_original:
            # Source was selected after info.xml: do not discard the deliberate
            # metadata selection. Only the Source path changes.
            self._a2_pending_dirty = True
            self.basic_dias_note.setText('Info.xml valgt: ' + str(self._a2_original))
            return
        self._a2_pending_values = {}
        self._a2_pending_dirty = False
        self._a2_original = candidate_info_xml(source) if source and Path(source).is_dir() else None
        self._a2_original_fields = {}
        if self._a2_original:
            try:
                self._a2_pending_values = read_original(self._a2_original)
                self._a2_original_fields = dict(self._a2_pending_values)
            except (ValueError, OSError):
                self._a2_original = None
        self._a2_pending_dirty = bool(self._a2_original)
        label = self._a2_pending_values.get('label') or ''
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
        self._a2_original_fields = {}
        if self._a2_original:
            try:
                self._a2_original_fields = read_original(self._a2_original)
            except (OSError, ValueError):
                pass
        self._a2_pending_values = values
        label = values.get('label') or ''
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
        job = self._a2_matching_job()
        values = current_values(job) if job and not self._a2_pending_dirty else dict(self._a2_pending_values)
        if self.basic_dias_label.text().strip():
            values = linked_values({**values, 'label': self.basic_dias_label.text().strip()})
        original = self._a2_original
        editor = InfoXmlEditor(self, values, original)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        self._a2_original = editor.original
        if self._a2_original and not self.basic_source_path.text().strip():
            self._a3_manually_loaded_info = True
        self._a2_original_fields = {}
        if self._a2_original:
            try:
                self._a2_original_fields = read_original(self._a2_original)
            except (OSError, ValueError):
                pass
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
        """Same API and runner as Advanced, with approved Work preflight."""
        from app.basic_start_v0111_a1 import (
            prepare_basic_plan, require_basic_arkade_cli, require_basic_siegfried,
            existing_basic_job, select_or_create_basic_job,
        )
        if self._basic_starting or self._worker is not None or self.api.running:
            return
        if self._basic_legacy_layout and not self._basic_selection_edited:
            QMessageBox.information(self, 'Eksisterende Work-oppsett',
                                    'Kjør denne jobben i Avansert modus.')
            return
        self._basic_starting = True
        self._a2_preserve_draft = True
        self.basic_run_button.setEnabled(False)
        started = False
        try:
            plan = prepare_basic_plan(
                self.basic_source_path.text(), self.basic_work_path.text(),
                self.api.settings, controls=self._selected_basic_controls())
            require_basic_arkade_cli(self.api, plan)
            require_basic_siegfried(self.api, plan)
            inspection = inspect_work(plan.work_operations, plan.source_extraction)
            match = existing_basic_job(self.api, plan)
            kind = ('same_job' if inspection.kind == 'unknown_job' and match is not None
                    else inspection.kind)
            if kind in ('different_source', 'unknown_job'):
                raise ValueError('Work har ukjent eller annen Source. Velg trygg Work-mappe.')
            if kind == 'same_job' and match is None:
                raise ValueError('Åpne den eksisterende jobblisten før Work gjenbrukes.')
            if kind != 'empty':
                token = getattr(self, '_a3_work_approval', None)
                if (token is None or not _same(token[0], plan.source_extraction)
                        or not _same(token[1], plan.work_operations)
                        or token[2] != kind):
                    raise ValueError('Velg og bekreft denne Work-mappen i Work-steget først.')
            if match is None and self.api.workspace().jobs:
                answer = QMessageBox.question(
                    self, 'Ny kontroll',
                    'Det er allerede andre jobber i jobblisten.\n\n'
                    'Opprette en egen jobbliste for dette uttrekket?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes or not self._maybe_save():
                    return
                self.api.new_job_list()
                self._active_id = None
            if (match is None and (inspection.kind == 'unrelated' or
                    (inspection.kind == 'empty' and inspection.count > 0
                     and work_contains_only_joblists(plan.work_operations)))):
                job_id, _created = self._a3_create_approved_job(plan)
            else:
                job_id, _created = select_or_create_basic_job(self.api, plan)
            self._basic_job_id = job_id
            self._basic_last_run_signal = None
            self._basic_last_run_message = ''
            self._basic_operation_fraction = None
            self._basic_operation_index = None
            self._active_id = job_id
            self._basic_selection_edited = False
            self._basic_legacy_layout = False
            self._refresh(force=True)
            status = self.api.job_details(job_id).job.status
            self._a3_auto_results_pending = self._a3_auto_results.isChecked()
            self._a3_autorun_armed = True
            if status == 'Venter ved kontrollpunkt':
                self._continue_job()
            else:
                # A2's _run_selected persists pending DIAS metadata first.
                self._run_selected()
            started = self._worker is not None or self.api.running
            if started:
                QTimer.singleShot(350, self._a3_auto_start_windows)
        except Exception as exc:
            QMessageBox.warning(self, 'Kunne ikke starte kontroll', str(exc))
        finally:
            if not started:
                self._a3_auto_results_pending = False
                self._a3_autorun_armed = False
            self._a2_preserve_draft = False
            self._basic_starting = False
            self._sync_basic_status()

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
