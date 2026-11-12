"""Low-threshold Noark 5 entry surface, sharing the existing Qt workbench.

Basic mode is presentation only. Advanced docks and tab pages remain the same
objects, and execution always goes through DwmMainWindow's existing preflight,
joblist persistence and worker path. No second execution engine is introduced.
"""
from __future__ import annotations

from pathlib import Path
import json
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget,
    QTreeWidget, QTreeWidgetItem, QHeaderView,
)

from app.basic_start_v0111_a1 import (
    BASIC_WORKFLOW_ID, BASIC_ARKADE_WORKFLOW_ID, BASIC_CONTROLS,
    basic_options_for_operations, existing_basic_job, normalize_basic_controls,
    prepare_basic_plan, require_basic_arkade_cli, require_basic_siegfried,
    select_or_create_basic_job,
)
from app.job_preflight_v018_a6 import check_extraction_folder
from app.basic_run_feedback_v0111_a3 import (
    operation_caption, latest_signal_text, sanitized_activity_message,
    elapsed_clock, planned_operation_rows,
)
from app.storage_profiles_v0110_a1 import suggest_known_source_work
from app.storage_profiles_v0110_a2 import resolve_storage_profile
from .main_window import DOCK_NAMES, DwmMainWindow as _AdvancedMainWindow
from .appearance_v0110_a3 import stylesheet_for


class DwmMainWindow(_AdvancedMainWindow):
    """Same main window and stateful API, with a genuinely uncluttered Basic mode."""

    def __init__(self, api, parent=None):
        super().__init__(api, parent)
        self._basic_active = False
        self._basic_advanced_state = None
        self._basic_advanced_page = self.pages.currentWidget()
        self._basic_job_id: str | None = None
        self._basic_selection_edited = False
        self._basic_legacy_layout = False
        self._basic_starting = False
        self._setting_basic_workflow = False
        self._basic_last_run_signal = None
        self._basic_last_run_message = ''
        self._basic_operation_fraction = None
        self._basic_operation_index = None
        self._basic_heartbeat_tick = 0
        self._build_basic_page()
        self._install_basic_menu_action()
        self._basic_timer = QTimer(self)
        self._basic_timer.setInterval(500)
        self._basic_timer.timeout.connect(self._sync_basic_status)
        self._basic_timer.start()
        if str(self.config.value('qt/v0111_interface_mode', 'basic')) != 'advanced':
            self._enter_basic()
        self._sync_basic_status()

    def _build_basic_page(self):
        # A fixed, compact running-status strip stays above the scrollable form.
        # It never owns execution state; advanced and Basic use the same API.
        page = QWidget(self)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(8, 8, 8, 8)
        page_layout.setSpacing(6)
        area = QScrollArea(page)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        area.setWidget(body)
        outer = QHBoxLayout(body)
        outer.setContentsMargins(16, 16, 16, 18)
        outer.addStretch(1)
        content = QWidget()
        content.setMaximumWidth(980)
        outer.addWidget(content, 8)
        outer.addStretch(1)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(18)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel('Kontroller et arkivuttrekk')
        title.setFont(QFont('Segoe UI', 19, QFont.Weight.DemiBold))
        title_block.addWidget(title)
        lead = QLabel('Tre steg for å kontrollere et Noark 5-uttrekk.')
        lead.setWordWrap(True)
        title_block.addWidget(lead)
        header.addLayout(title_block, 1)
        self.basic_advanced_button = QPushButton('Avansert modus')
        self.basic_advanced_button.clicked.connect(self._leave_basic)
        header.addWidget(self.basic_advanced_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        source_group = QGroupBox('1   Velg uttrekk (Source)')
        source_layout = QVBoxLayout(source_group)
        source_layout.setSpacing(8)
        source_layout.addWidget(self._basic_note(
            'Velg mappen som inneholder selve Noark 5-uttrekket. Originalfilene endres ikke.'
        ))
        source_row = QHBoxLayout()
        self.basic_source_path = self._path_editor('Ingen uttrekksmappe valgt')
        source_row.addWidget(self.basic_source_path, 1)
        self.basic_choose_source = QPushButton('Finn uttrekk…')
        self.basic_choose_source.clicked.connect(self._choose_basic_source)
        source_row.addWidget(self.basic_choose_source)
        source_layout.addLayout(source_row)
        self.basic_source_hint = self._basic_note('')
        source_layout.addWidget(self.basic_source_hint)
        layout.addWidget(source_group)

        work_group = QGroupBox('2   Velg arbeidsmappe (Work)')
        work_layout = QVBoxLayout(work_group)
        work_layout.setSpacing(8)
        work_layout.addWidget(self._basic_note(
            'Her lagres kontrollresultater og jobbdata, separat fra originaluttrekket.'
        ))
        work_row = QHBoxLayout()
        self.basic_work_path = self._path_editor('Ingen arbeidsmappe valgt')
        work_row.addWidget(self.basic_work_path, 1)
        self.basic_choose_work = QPushButton('Velg Work…')
        self.basic_choose_work.clicked.connect(self._choose_basic_work)
        work_row.addWidget(self.basic_choose_work)
        work_layout.addLayout(work_row)
        self.basic_work_hint = self._basic_note('Valgt mappe brukes direkte til kontrollresultater. Ingen ekstra Work-/DWM-/jobbmapper legges til.')
        work_layout.addWidget(self.basic_work_hint)
        layout.addWidget(work_group)

        run_group = QGroupBox('3   Start kontroll')
        run_layout = QVBoxLayout(run_group)
        run_layout.setSpacing(9)
        run_layout.addWidget(QLabel('Velg kontroller:'))
        self.basic_option_checks = {}
        labels = (
            ('dwm', 'DWM – Noark 5-test og depotrapport'),
            ('siegfried', 'Siegfried – PRONOM filidentifikasjon'),
            ('arkade_noark5', 'Arkade 5 CLI – Noark 5-test'),
            ('arkade_pronom', 'Arkade 5 CLI – PRONOM-analyse'),
        )
        stored = self.config.value('qt/v0111_basic_options', '')
        if stored:
            try:
                selected = normalize_basic_controls(json.loads(str(stored)))
            except (ValueError, TypeError):
                selected = ('dwm',)
        else:
            # Preserve the old two-profile preference for existing a2 users.
            legacy = str(self.config.value('qt/v0111_basic_workflow_id', BASIC_WORKFLOW_ID)
                         or BASIC_WORKFLOW_ID)
            selected = (('dwm', 'arkade_noark5', 'arkade_pronom')
                        if legacy == BASIC_ARKADE_WORKFLOW_ID else ('dwm',))
        self._setting_basic_workflow = True
        for key, caption in labels:
            check = QCheckBox(caption)
            check.setChecked(key in selected)
            check.setToolTip('Kun denne kontrollen aktiveres/deaktiveres.')
            self.basic_option_checks[key] = check
            run_layout.addWidget(check)
        self._setting_basic_workflow = False
        self.basic_workflow_description = self._basic_note('')
        run_layout.addWidget(self.basic_workflow_description)
        for check in self.basic_option_checks.values():
            check.toggled.connect(self._basic_workflow_changed)
        self._basic_workflow_changed(initializing=True)
        commands = QHBoxLayout()
        self.basic_run_button = QPushButton('Start kontroll')
        self.basic_run_button.setMinimumHeight(38)
        self.basic_run_button.clicked.connect(self._start_basic_control)
        commands.addWidget(self.basic_run_button)
        self.basic_stop_button = QPushButton('Stopp kjøring')
        self.basic_stop_button.clicked.connect(self._request_stop)
        commands.addWidget(self.basic_stop_button)
        commands.addStretch(1)
        self.basic_results_button = QPushButton('Se resultatvisninger…')
        self.basic_results_button.clicked.connect(self._open_basic_results)
        commands.addWidget(self.basic_results_button)
        self.basic_details_button = QPushButton('Kjøredetaljer…')
        self.basic_details_button.clicked.connect(self._open_basic_run_details)
        commands.addWidget(self.basic_details_button)
        run_layout.addLayout(commands)
        self.basic_status = QLabel('Velg uttrekksmappe og Work-mappe for å begynne.')
        self.basic_status.setWordWrap(True)
        self.basic_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        run_layout.addWidget(self.basic_status)
        self.basic_progress = QProgressBar()
        self.basic_progress.setRange(0, 100)
        self.basic_progress.setValue(0)
        run_layout.addWidget(self.basic_progress)
        # The main bar tracks completed steps. This second bar tracks only
        # genuine progress events inside the active step (or stays busy).
        self.basic_active_operation = self._basic_note('')
        run_layout.addWidget(self.basic_active_operation)
        self.basic_operation_progress = QProgressBar()
        self.basic_operation_progress.setRange(0, 0)
        self.basic_operation_progress.setMinimumHeight(17)
        run_layout.addWidget(self.basic_operation_progress)
        self.basic_activity = self._basic_note('')
        run_layout.addWidget(self.basic_activity)
        for control in (self.basic_active_operation, self.basic_operation_progress,
                        self.basic_activity):
            control.hide()
        run_layout.addWidget(self._basic_note(
            'Før første kjøring vil DWM be om godkjenning av eventuelle nye Work-mapper '
            'og lagring av jobblisten. Fullført kontroll betyr ikke faglig godkjent uttrekk.'
        ))
        layout.addWidget(run_group)
        layout.addStretch(1)
        self._build_basic_pinned_status(page, page_layout)
        page_layout.addWidget(area, 1)
        self.pages.addTab(page, 'Enkel start')
        self._basic_page = page
        self.basic_choose_work.setEnabled(False)
        self.basic_run_button.setEnabled(False)
        self.basic_stop_button.setEnabled(False)
        self.basic_results_button.setEnabled(False)
        self.basic_details_button.setEnabled(False)

    def _build_basic_pinned_status(self, page, parent_layout):
        # No status/progress widget is moved between Qt parents. The visible
        # Basic strip mirrors existing run events; there is one execution engine.
        panel = QFrame(page)
        panel.setObjectName('basicPinnedRunStatus')
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        content = QVBoxLayout(panel)
        content.setContentsMargins(12, 8, 12, 8)
        content.setSpacing(4)

        header = QHBoxLayout()
        heading = QLabel('Kjørestatus')
        heading.setFont(QFont('Segoe UI', 11, QFont.Weight.DemiBold))
        header.addWidget(heading)
        header.addStretch(1)
        self.basic_pinned_details_button = QPushButton('Kjøredetaljer…')
        self.basic_pinned_details_button.clicked.connect(self._open_basic_run_details)
        header.addWidget(self.basic_pinned_details_button)
        self.basic_pinned_stop_button = QPushButton('Stopp kjøring')
        self.basic_pinned_stop_button.clicked.connect(self._request_stop)
        header.addWidget(self.basic_pinned_stop_button)
        content.addLayout(header)

        self.basic_pinned_status = self._basic_note('')
        content.addWidget(self.basic_pinned_status)
        self.basic_pinned_progress = QProgressBar()
        self.basic_pinned_progress.setRange(0, 100)
        content.addWidget(self.basic_pinned_progress)
        self.basic_pinned_operation = self._basic_note('')
        content.addWidget(self.basic_pinned_operation)
        self.basic_pinned_operation_progress = QProgressBar()
        self.basic_pinned_operation_progress.setRange(0, 0)
        self.basic_pinned_operation_progress.setMinimumHeight(15)
        content.addWidget(self.basic_pinned_operation_progress)

        last_row = QHBoxLayout()
        last_row.addWidget(QLabel('Tid siden faktisk kjøremelding:'))
        self.basic_pinned_elapsed = QLabel('--:--:--')
        self.basic_pinned_elapsed.setObjectName('basicLastRealRunSignal')
        self.basic_pinned_elapsed.setMinimumWidth(86)
        self.basic_pinned_elapsed.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.basic_pinned_elapsed.setFont(QFont('Consolas', 10))
        last_row.addWidget(self.basic_pinned_elapsed)
        last_row.addStretch(1)
        content.addLayout(last_row)
        self.basic_pinned_message = QLabel('')
        self.basic_pinned_message.setObjectName('basicLastRunMessage')
        self.basic_pinned_message.setWordWrap(False)
        self.basic_pinned_message.setMaximumHeight(26)
        self.basic_pinned_message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.addWidget(self.basic_pinned_message)
        parent_layout.addWidget(panel)
        panel.hide()
        self.basic_pinned_panel = panel

    @staticmethod
    def _basic_note(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @staticmethod
    def _path_editor(placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setReadOnly(True)
        field.setPlaceholderText(placeholder)
        field.textChanged.connect(field.setToolTip)
        return field

    def _install_basic_menu_action(self):
        self.basic_mode_action = QAction('Enkel start', self)
        self.basic_mode_action.triggered.connect(self._enter_basic)
        for action in self.menuBar().actions():
            menu = action.menu()
            if menu is not None and menu.title().replace('&', '') == 'Vis':
                before = menu.actions()
                if before:
                    menu.insertAction(before[0], self.basic_mode_action)
                else:
                    menu.addAction(self.basic_mode_action)
                return
        self.menuBar().addAction(self.basic_mode_action)

    def _a8_show_job_log(self):
        # The original runtime auto-shows the activity dock for run.started.
        # In Basic, that would cover the three-step screen during the run.
        if getattr(self, '_basic_active', False):
            return
        return super()._a8_show_job_log()

    def _a8_process_run_event(self, event):
        # Reuse the existing main-window event handling and run logs.
        super()._a8_process_run_event(event)
        if not getattr(self, '_basic_job_id', None):
            return
        if str(getattr(event, 'job_id', '') or '') != self._basic_job_id:
            return
        kind = str(getattr(event, 'kind', '') or '')
        if kind not in ('run.started', 'run.progress', 'run.log', 'run.state',
                        'run.cancel_requested', 'run.finished', 'run.error'):
            return
        self._basic_last_run_signal = time.monotonic()
        if kind == 'run.started':
            self._basic_operation_fraction = None
            self._basic_operation_index = None
            self._basic_last_run_message = 'Kjøringen er startet.'
        elif kind == 'run.progress':
            value = getattr(event, 'progress', None)
            if isinstance(value, (int, float)) and 0 <= value <= 1:
                self._basic_operation_fraction = float(value)
            message = sanitized_activity_message(getattr(event, 'message', ''), kind)
            if message:
                self._basic_last_run_message = message
        elif kind == 'run.log':
            message = sanitized_activity_message(getattr(event, 'message', ''), kind)
            if message:
                if message.startswith('START:'):
                    self._basic_operation_fraction = None
                self._basic_last_run_message = message
        elif kind in ('run.finished', 'run.error'):
            self._basic_operation_fraction = None
            message = sanitized_activity_message(getattr(event, 'message', ''), kind)
            if message:
                self._basic_last_run_message = message
        elif kind == 'run.cancel_requested':
            self._basic_last_run_message = (
                'Stopp er forespurt. Deljobben avsluttes når det er mulig.'
            )

    def _enter_basic(self):
        if self._basic_active:
            return
        # Snapshot the native advanced layout BEFORE hiding any dock. It is
        # restored on exit and persisted on close even when Basic is active.
        self._basic_advanced_state = self.saveState(4)
        if self.pages.currentWidget() is not self._basic_page:
            self._basic_advanced_page = self.pages.currentWidget()
        self._basic_active = True
        for name in DOCK_NAMES:
            getattr(self, 'dock_' + name).hide()
        self.pages.setCurrentWidget(self._basic_page)
        self.pages.tabBar().hide()
        self._toolbar.hide()
        self.menuBar().hide()
        self.statusBar().hide()
        self.config.setValue('qt/v0111_interface_mode', 'basic')
        if not self._basic_selection_edited:
            self._load_basic_active_job()
        self._sync_basic_status()

    def _leave_basic(self):
        if not self._basic_active:
            return
        self._basic_active = False
        self.menuBar().show()
        self._toolbar.show()
        self.statusBar().show()
        self.pages.tabBar().show()
        target = self._basic_advanced_page
        if target is not None and target is not self._basic_page:
            self.pages.setCurrentWidget(target)
        else:
            self.pages.setCurrentIndex(1)
        if self._basic_advanced_state is not None:
            self.restoreState(self._basic_advanced_state, 4)
        self.config.setValue('qt/v0111_interface_mode', 'advanced')
        self._refresh(force=True)

    def _reset_basic_selection(self):
        self._basic_job_id = None
        self._basic_selection_edited = False
        self._basic_legacy_layout = False
        self.basic_source_path.clear()
        self.basic_work_path.clear()
        self.basic_source_hint.clear()
        self.basic_work_hint.setText('Velg en tom Work-mappe. Valgt mappe brukes direkte.')
        self.basic_choose_work.setEnabled(False)

    def _selected_basic_controls(self):
        return tuple(key for key in BASIC_CONTROLS
                     if self.basic_option_checks[key].isChecked())

    def _basic_workflow_changed(self, _index=None, *, initializing=False):
        selected = self._selected_basic_controls()
        if not selected:
            self.basic_workflow_description.setText('Velg minst én kontroll.')
        else:
            notes = ['Resultatene lagres under valgt Work.']
            if 'siegfried' in selected:
                notes.append('Siegfried bruker installert sf.exe; resultatene blir egen DWM-evidens.')
            if 'arkade_noark5' in selected or 'arkade_pronom' in selected:
                notes.append('Arkade 5 CLI må være konfigurert i Setup.')
            if 'dwm' not in selected:
                notes.append('Uten DWM-kontrollen produseres ingen DWM-depotrapport.')
            notes.append('AIP inngår ikke.')
            self.basic_workflow_description.setText(' '.join(notes))
        if not initializing and not self._setting_basic_workflow:
            self.config.setValue('qt/v0111_basic_options', json.dumps(selected))
            self._basic_selection_edited = True
            self._basic_job_id = None
            self._sync_basic_status()

    def _open_path(self, path: str):
        # The base constructor may call this before the Basic panel exists.
        before = self.api.workspace().job_list_path
        super()._open_path(path)
        if hasattr(self, 'basic_source_path') and self.api.workspace().job_list_path != before:
            self._reset_basic_selection()
            self._load_basic_active_job()
            self._sync_basic_status()

    def _new_list(self):
        before = self.api.workspace()
        super()._new_list()
        after = self.api.workspace()
        if (hasattr(self, 'basic_source_path') and
                (after.job_list_path != before.job_list_path or after.jobs != before.jobs)):
            self._reset_basic_selection()
            self._sync_basic_status()

    def _load_basic_active_job(self):
        job_id = self._active_id
        if not job_id:
            return
        try:
            details = self.api.job_details(job_id)
        except Exception:
            return
        job = details.job
        if not job.source_extraction:
            return
        self._basic_job_id = job_id
        self.basic_source_path.setText(str(job.source_extraction))
        chosen_work = job.work_operations or job.work_root
        actual_work = job.effective_work_operations
        self._basic_legacy_layout = bool(
            chosen_work and actual_work and
            Path(chosen_work).resolve(strict=False) != Path(actual_work).resolve(strict=False)
        )
        self.basic_work_path.setText(str(chosen_work or ''))
        self.basic_choose_work.setEnabled(True)
        if chosen_work:
            if self._basic_legacy_layout:
                self.basic_work_hint.setText(
                    'Eksisterende jobb bruker avansert Work-struktur: ' + str(actual_work)
                    + '. Bruk Avansert modus for denne jobben.'
                )
            else:
                self._preview_basic_work()
        self.basic_source_hint.setText('Eksisterende jobb: ' + job.name)
        try:
            current_ids = tuple(op.operation_id for op in details.operations)
            selected = basic_options_for_operations(current_ids)
            if selected:
                self._setting_basic_workflow = True
                try:
                    for key, widget in self.basic_option_checks.items():
                        widget.setChecked(key in selected)
                    self._basic_workflow_changed(initializing=True)
                finally:
                    self._setting_basic_workflow = False
        except (ValueError, RuntimeError):
            pass
        self._basic_selection_edited = False

    def _choose_basic_source(self):
        if self._worker is not None or self.api.running:
            return
        source = QFileDialog.getExistingDirectory(
            self, 'Velg Noark 5-uttrekksmappe',
            str(self.config.value('qt/last_new_source_dir', '') or ''),
        )
        if not source:
            return
        try:
            issues = check_extraction_folder(source, profile_id='noark5')
        except Exception as exc:
            QMessageBox.warning(self, 'Kunne ikke lese uttrekket', str(exc))
            return
        if issues:
            QMessageBox.warning(self, 'Dette er ikke en Noark 5-uttrekksmappe',
                                '\n\n'.join(issue.message for issue in issues))
            return
        self.config.setValue('qt/last_new_source_dir', source)
        self.basic_source_path.setText(source)
        self.basic_work_path.clear()  # Never reuse another extraction's Work by accident.
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
                    'Mulig plassering: ' + str(roles['work_root'])
                    + '. Basic bruker mappen du velger direkte, uten ekstra mellommapper.'
                )
        except (ValueError, OSError):
            pass
        self._sync_basic_status()

    def _choose_basic_work(self):
        if not self.basic_source_path.text() or self._worker is not None or self.api.running:
            return
        selected = QFileDialog.getExistingDirectory(
            self, 'Velg eksisterende Work-mappe',
            str(self.config.value('qt/last_work_dir', '') or ''),
        )
        if not selected:
            return
        try:
            plan = prepare_basic_plan(
                self.basic_source_path.text(), selected, self.api.settings,
            )
        except Exception as exc:
            QMessageBox.warning(self, 'Ugyldig Work-plassering', str(exc))
            return
        self.config.setValue('qt/last_work_dir', selected)
        self.basic_work_path.setText(selected)
        self._basic_job_id = None
        self._basic_legacy_layout = False
        self._basic_selection_edited = True
        self.basic_work_hint.setText('Work brukes direkte: ' + str(plan.work_operations) + ' (ingen ekstra mellommapper)')
        self._sync_basic_status()

    def _preview_basic_work(self):
        if not self.basic_source_path.text() or not self.basic_work_path.text():
            return
        try:
            plan = prepare_basic_plan(
                self.basic_source_path.text(), self.basic_work_path.text(), self.api.settings,
            )
        except Exception as exc:
            self.basic_work_hint.setText('Kontroller Work-plasseringen: ' + str(exc))
        else:
            self.basic_work_hint.setText('Work brukes direkte: ' + str(plan.work_operations) + ' (ingen ekstra mellommapper)')

    def _start_basic_control(self):
        if self._basic_starting or self._worker is not None or self.api.running:
            return
        if self._basic_legacy_layout and not self._basic_selection_edited:
            QMessageBox.information(
                self, 'Eksisterende Work-oppsett',
                'Den valgte jobben har et avansert Work-oppsett med undermapper. '
                'Kjør den i Avansert modus eller velg en annen, tom Work-mappe. '
                'DWM flytter ikke eksisterende jobber automatisk.'
            )
            return
        self._basic_starting = True
        self.basic_run_button.setEnabled(False)
        try:
            plan = prepare_basic_plan(
                self.basic_source_path.text(), self.basic_work_path.text(), self.api.settings,
                controls=self._selected_basic_controls(),
            )
            # Fail before prompting to replace the open job list. The API
            # caches the CLI probe, and select_or_create checks again for safety.
            require_basic_arkade_cli(self.api, plan)
            require_basic_siegfried(self.api, plan)
            # Basic handles one extraction at a time. Do not silently append
            # a new extraction to an unrelated, previously opened job list.
            match = existing_basic_job(self.api, plan)
            if match is None and self.api.workspace().jobs:
                answer = QMessageBox.question(
                    self, 'Ny kontroll',
                    'Det er allerede en jobbliste med andre jobber åpen.\n\n'
                    'Opprette en egen jobbliste for dette uttrekket?\n'
                    'Den nåværende jobblisten kan lagres før byttet.',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                if not self._maybe_save():
                    return
                self.api.new_job_list()
                self._active_id = None
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
            state = self.api.job_details(job_id).job.status
            if state == 'Venter ved kontrollpunkt':
                self._continue_job()
            else:
                # Uses the existing preflight, approval, save and worker path.
                self._run_selected()
        except Exception as exc:
            QMessageBox.warning(self, 'Kunne ikke starte kontroll', str(exc))
        finally:
            self._basic_starting = False
            self._sync_basic_status()

    def _open_setup(self):
        if self._worker is not None or self.api.running:
            QMessageBox.information(self, 'Setup', 'Avslutt kjøringen før du endrer Setup.')
            return
        from .setup_format_v0111_a2 import DwmSetupDialog
        dialog = DwmSetupDialog(self.api, self)
        self._a3_place_dialog(dialog, 'setup')
        QTimer.singleShot(0, lambda: self._a3_place_dialog(dialog, 'setup'))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._a3_apply_display_preferences()
            self._refresh(force=True)

    def _a12_open_result_center(self, _checked=False, *, depot=False):
        if not self._active_id:
            QMessageBox.information(self, 'Resultatvisninger', 'Velg en jobb i jobblisten.')
            return
        try:
            job = self.api.job_details(self._active_id).job
        except Exception as exc:
            QMessageBox.warning(self, 'Resultatvisninger', str(exc))
            return
        from .result_center_siegfried_v0111_a3 import ResultCenterWindow
        from app.format_assessment_v0111_a2 import chosen_format_source
        dialog = ResultCenterWindow(
            job.effective_work_operations,
            display_name=job.job_id + ' - ' + job.name,
            available_jobs=self.api.report_candidates(),
            report_api=self.api,
            on_generate_report=self._a12_open_selected_report,
            format_assessment_source=chosen_format_source(self.api.settings),
        )
        # A Basic job with only one external test should open on the relevant
        # evidence source rather than an empty DWM depot summary.
        try:
            ids = {item.operation_id for item in self.api.job_details(self._active_id).operations}
            if 'run_noark5_xpath_tests_2026' not in ids:
                if 'siegfried_pronom_identification' in ids:
                    dialog.tabs.setCurrentWidget(dialog._sf_page)
                elif 'arkade5_pronom_analysis' in ids:
                    dialog.tabs.setCurrentWidget(dialog._pages['PRONOM'])
                elif 'arkade5_noark5_test' in ids:
                    dialog.tabs.setCurrentWidget(dialog._pages['Arkade 5'])
        except (RuntimeError, AttributeError, ValueError):
            pass
        if depot:
            dialog.show_depot_review()
        dialog.setStyleSheet(stylesheet_for(self.api.settings))
        dialog.setFont(self.font())
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._a12_result_windows.append(dialog)
        dialog.destroyed.connect(
            lambda _obj=None, win=dialog: (
                self._a12_result_windows.remove(win)
                if win in self._a12_result_windows else None
            )
        )
        dialog.show()
        self._a3_place_dialog(dialog, 'results')

    def _open_basic_run_details(self):
        """Open the existing Advanced Kjøreløp view over the SAME API events.

        No second logger, job runner, or copied result files. The standalone
        viewer already exposes actual run history and the saved log/results.
        """
        if not self._basic_job_id:
            return
        self._active_id = self._basic_job_id
        viewer = getattr(self, '_detached_run_window', None)
        if viewer is None:
            # Existing Advanced viewer: same history, event log and callbacks.
            self._a9_float_run()
            viewer = getattr(self, '_detached_run_window', None)
            if getattr(self, '_basic_active', False):
                for name in DOCK_NAMES:
                    getattr(self, 'dock_' + name).hide()
        else:
            viewer.show()
            viewer.raise_()
            viewer.activateWindow()
        if viewer is None:
            return
        viewer.setWindowTitle('Kjøredetaljer – ' + self._basic_job_id)
        self._basic_add_run_plan(viewer)
        self._basic_sync_run_plan()
        self._a9_sync_detached_run()

    def _basic_add_run_plan(self, viewer):
        """Add pending/active operations beside the existing actual-run history."""
        if getattr(viewer, '_basic_plan_tree', None) is not None:
            return
        label = QLabel('Alle deljobber – gjeldende jobbstatus')
        label.setObjectName('basicPlanCaption')
        tree = QTreeWidget(viewer)
        tree.setObjectName('basicRunPlan')
        tree.setHeaderLabels(['Nr.', 'Deljobb', 'Status'])
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.setMinimumHeight(120)
        tree.setMaximumHeight(240)
        header = tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        # The window's existing splitter below still shows actual run history
        # and the run-event log. No ownership changes to those widgets.
        viewer.layout().insertWidget(2, label)
        viewer.layout().insertWidget(3, tree)
        viewer._basic_plan_tree = tree
        viewer._basic_plan_key = None

    def _basic_sync_run_plan(self):
        viewer = getattr(self, '_detached_run_window', None)
        tree = getattr(viewer, '_basic_plan_tree', None) if viewer is not None else None
        if tree is None or not self._basic_job_id:
            return
        try:
            details = self.api.job_details(self._basic_job_id)
            rows = planned_operation_rows(details.operations, details.job.status,
                                          details.job.current_operation)
        except (AttributeError, KeyError, RuntimeError, ValueError):
            return
        # Preserve selection/scroll positions on 500 ms updates. Only rebuild
        # when the workflow itself changes. Do not blink an entire tree.
        key = tuple((number, name, op_id) for number, name, _status, op_id in rows)
        if key != viewer._basic_plan_key:
            tree.clear()
            for number, name, status, _op_id in rows:
                tree.addTopLevelItem(QTreeWidgetItem([str(number), name, status]))
            viewer._basic_plan_key = key
        else:
            for index, (_number, _name, status, _op_id) in enumerate(rows):
                item = tree.topLevelItem(index)
                if item is not None and item.text(2) != status:
                    item.setText(2, status)

    def _a9_redock_run(self):
        # Closing the existing Kjøreløp window must not reveal an Advanced
        # dock over the Basic three-step screen. Advanced mode is unchanged.
        super()._a9_redock_run()
        if getattr(self, '_basic_active', False):
            for name in DOCK_NAMES:
                getattr(self, 'dock_' + name).hide()

    def _a11_open_history_log(self, key: str):
        # Reuse the SAME Work-backed log selection as Advanced. The default
        # Basic suppression of auto-opening the log dock must not suppress an
        # explicit click on "Logg" in the detached Kjøreløp viewer.
        if not key or '|' not in key:
            return
        if getattr(self, '_basic_active', False):
            # Populate the same run-id choices before Advanced selects the log.
            self._a8_refresh_job_log(force=True)
        super()._a11_open_history_log(key)
        if getattr(self, '_basic_active', False):
            if self._detached_log_window is None:
                self._a8_float_job_log()
            else:
                self._detached_log_window.show()
                self._detached_log_window.raise_()
                self._a8_refresh_job_log(force=True)
            for name in DOCK_NAMES:
                getattr(self, 'dock_' + name).hide()

    def _a9_redock_job_log(self):
        super()._a9_redock_job_log()
        if getattr(self, '_basic_active', False):
            for name in DOCK_NAMES:
                getattr(self, 'dock_' + name).hide()

    def _open_basic_results(self):
        if not self._basic_job_id:
            return
        self._active_id = self._basic_job_id
        self._refresh(force=True)
        self._a12_open_result_center()

    def _sync_basic_status(self):
        if not hasattr(self, 'basic_run_button'):
            return
        busy = self._worker is not None or self.api.running or self._basic_starting
        self.basic_choose_source.setEnabled(not busy)
        self.basic_choose_work.setEnabled(not busy and bool(self.basic_source_path.text()))
        self.basic_run_button.setEnabled(
            not busy and bool(self._selected_basic_controls())
            and not getattr(self, '_basic_legacy_layout', False)
            and bool(self.basic_source_path.text()) and bool(self.basic_work_path.text())
        )
        self.basic_stop_button.setEnabled(busy)
        # The running status is pinned above the scrollable three-step form.
        # Legacy status controls remain for completed/idle jobs and tests.
        if hasattr(self, 'basic_pinned_panel'):
            self.basic_pinned_panel.setVisible(bool(busy and self._basic_active))
            self.basic_pinned_stop_button.setEnabled(busy)
            self.basic_status.setVisible(not busy)
            self.basic_progress.setVisible(not busy)
            self.basic_stop_button.setVisible(not busy)
            self.basic_details_button.setVisible(not busy)
        for control in (self.basic_active_operation, self.basic_operation_progress,
                        self.basic_activity):
            control.setVisible(bool(busy and not hasattr(self, 'basic_pinned_panel')))
        job = None
        if self._basic_job_id:
            try:
                job = next((item for item in self.api.workspace().jobs
                            if item.job_id == self._basic_job_id), None)
            except Exception:
                job = None
        if job is None:
            if hasattr(self, 'basic_pinned_panel'):
                self.basic_pinned_panel.hide()
            if hasattr(self, 'basic_details_button'):
                self.basic_details_button.setEnabled(False)
            self.basic_results_button.setEnabled(False)
            self.basic_progress.setValue(0)
            if not self._selected_basic_controls():
                self.basic_status.setText('Velg minst én kontroll.')
            elif self.basic_source_path.text() and self.basic_work_path.text():
                self.basic_status.setText('Klar til kontroll. Trykk Start kontroll.')
            elif self.basic_source_path.text():
                self.basic_status.setText('Velg Work-mappe for å fortsette.')
            else:
                self.basic_status.setText('Velg uttrekksmappe og Work-mappe for å begynne.')
            self.basic_run_button.setText('Start kontroll')
            return
        self.basic_progress.setValue(max(0, min(100, round(job.progress * 100))))
        if hasattr(self, 'basic_details_button'):
            self.basic_details_button.setEnabled(True)
        self.basic_results_button.setEnabled(job.status in ('Ferdig', 'Feil', 'Hoppet over'))
        if job.status == 'Venter ved kontrollpunkt':
            self.basic_run_button.setText('Fortsett kontroll')
        elif job.status in ('Ferdig', 'Feil', 'Hoppet over'):
            self.basic_run_button.setText('Kjør kontroll på nytt')
        else:
            self.basic_run_button.setText('Start kontroll')
        text = f'{job.job_id} · {job.status} · {job.progress:.0%} fullført'
        if busy:
            try:
                operations = self.api.job_details(self._basic_job_id).operations
            except (AttributeError, KeyError, RuntimeError, ValueError):
                operations = ()
            completed = max(0, int(getattr(job, 'current_operation', 0) or 0))
            total = int(getattr(job, 'operation_count', 0) or 0)
            self.basic_active_operation.setText(
                operation_caption(operations, completed, total)
            )
            # A step's measured progress is distinct from the persisted overall
            # job.progress. Never increment progress just because time passes.
            if self._basic_operation_index != completed:
                self._basic_operation_index = completed
                self._basic_operation_fraction = None
            if self._basic_operation_fraction is None:
                self.basic_operation_progress.setRange(0, 0)
            else:
                self.basic_operation_progress.setRange(0, 100)
                self.basic_operation_progress.setValue(round(100 * self._basic_operation_fraction))
            # Never change decorative dots to suggest activity. Only a new
            # runner event resets the actual-signal clock.
            signal = latest_signal_text(self._basic_last_run_signal, time.monotonic())
            detail = self._basic_last_run_message or 'Venter på første kjøremelding.'
            self.basic_activity.setText(
                f'{signal}\nSiste melding: {detail}'
            )
            text += f' ({completed} av {total} deljobber fullført)'
        if getattr(self, '_basic_legacy_layout', False):
            text += ' – Eksisterende Work-struktur: kjør jobben i Avansert modus.'
        if job.status == 'Ferdig':
            text += ' – Gå gjennom resultatene før faglig vurdering.'
        elif job.status == 'Feil':
            text += ' – Kontrollene må gjennomgås.'
        self.basic_status.setText(text)
        if hasattr(self, 'basic_pinned_panel') and busy:
            self.basic_pinned_status.setText(text)
            self.basic_pinned_progress.setValue(self.basic_progress.value())
            self.basic_pinned_operation.setText(self.basic_active_operation.text())
            if self._basic_operation_fraction is None:
                self.basic_pinned_operation_progress.setRange(0, 0)
            else:
                self.basic_pinned_operation_progress.setRange(0, 100)
                self.basic_pinned_operation_progress.setValue(
                    round(100 * self._basic_operation_fraction))
            self.basic_pinned_elapsed.setText(
                elapsed_clock(self._basic_last_run_signal, time.monotonic()))
            self.basic_pinned_message.setText('Siste melding: ' + (
                self._basic_last_run_message or 'Venter på første kjøremelding.'))
            self.basic_pinned_message.setToolTip(self._basic_last_run_message or '')
        if hasattr(self, '_basic_sync_run_plan'):
            self._basic_sync_run_plan()

    def closeEvent(self, event):
        # The old main_window.closeEvent always persists saveState(). In Basic,
        # that contains hidden docks; preserve the real advanced arrangement.
        advanced_state = self._basic_advanced_state if self._basic_active else None
        super().closeEvent(event)
        if event.isAccepted() and advanced_state is not None:
            self.config.setValue('qt/window_state', advanced_state)
            self.config.sync()
