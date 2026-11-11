"""Low-threshold Noark 5 entry surface, sharing the existing Qt workbench.

Basic mode is presentation only. Advanced docks and tab pages remain the same
objects, and execution always goes through DwmMainWindow's existing preflight,
joblist persistence and worker path. No second execution engine is introduced.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from app.basic_start_v0111_a1 import (
    BASIC_WORKFLOW_ID, BASIC_ARKADE_WORKFLOW_ID, existing_basic_job,
    prepare_basic_plan, require_basic_arkade_cli, select_or_create_basic_job,
)
from app.job_preflight_v018_a6 import check_extraction_folder
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
        area = QScrollArea(self)
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
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel('Kontrollprofil:'))
        self.basic_workflow = QComboBox()
        self.basic_workflow.addItem('DWM standard', BASIC_WORKFLOW_ID)
        self.basic_workflow.addItem('DWM + Arkade 5 (Noark 5 og PRONOM)',
                                    BASIC_ARKADE_WORKFLOW_ID)
        stored = str(self.config.value('qt/v0111_basic_workflow_id', BASIC_WORKFLOW_ID)
                     or BASIC_WORKFLOW_ID)
        initial = self.basic_workflow.findData(stored)
        self.basic_workflow.setCurrentIndex(max(0, initial))
        profile_row.addWidget(self.basic_workflow, 1)
        run_layout.addLayout(profile_row)
        self.basic_workflow_description = self._basic_note('')
        run_layout.addWidget(self.basic_workflow_description)
        self.basic_workflow.currentIndexChanged.connect(self._basic_workflow_changed)
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
        run_layout.addLayout(commands)
        self.basic_status = QLabel('Velg uttrekksmappe og Work-mappe for å begynne.')
        self.basic_status.setWordWrap(True)
        self.basic_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        run_layout.addWidget(self.basic_status)
        self.basic_progress = QProgressBar()
        self.basic_progress.setRange(0, 100)
        self.basic_progress.setValue(0)
        run_layout.addWidget(self.basic_progress)
        run_layout.addWidget(self._basic_note(
            'Før første kjøring vil DWM be om godkjenning av eventuelle nye Work-mapper '
            'og lagring av jobblisten. Fullført kontroll betyr ikke faglig godkjent uttrekk.'
        ))
        layout.addWidget(run_group)
        layout.addStretch(1)
        self.pages.addTab(area, 'Enkel start')
        self._basic_page = area
        self.basic_choose_work.setEnabled(False)
        self.basic_run_button.setEnabled(False)
        self.basic_stop_button.setEnabled(False)
        self.basic_results_button.setEnabled(False)

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

    def _basic_workflow_changed(self, _index=None, *, initializing=False):
        selected = str(self.basic_workflow.currentData() or BASIC_WORKFLOW_ID)
        if selected == BASIC_ARKADE_WORKFLOW_ID:
            self.basic_workflow_description.setText(
                'DWM-kontroller og Arkade 5 CLI: Noark 5-test og PRONOM/Siegfried. '
                'Resultater lagres under valgt Work. Arkade 5 CLI må være konfigurert i Setup. '
                'AIP-produksjon er ikke inkludert.'
            )
        else:
            self.basic_workflow_description.setText(
                'Metadata, XML/XSD, arkivstruktur, Noark 5-tester og depotrapport. '
                'Arkade 5 og AIP-produksjon er ikke inkludert.'
            )
        if not initializing and not self._setting_basic_workflow:
            self.config.setValue('qt/v0111_basic_workflow_id', selected)
            self._basic_selection_edited = True
            self._basic_job_id = None  # Never display stale progress for a different workflow.
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
            from app.workflow_sequences import workflow_sequence_by_id
            current_ids = tuple(op.operation_id for op in details.operations)
            for sequence_id in (BASIC_WORKFLOW_ID, BASIC_ARKADE_WORKFLOW_ID):
                seq = workflow_sequence_by_id(sequence_id)
                if seq is not None and current_ids == tuple(seq.operation_ids):
                    index = self.basic_workflow.findData(sequence_id)
                    if index >= 0:
                        self._setting_basic_workflow = True
                        try:
                            self.basic_workflow.setCurrentIndex(index)
                        finally:
                            self._setting_basic_workflow = False
                    break
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
                workflow_id=str(self.basic_workflow.currentData() or BASIC_WORKFLOW_ID),
            )
            # Fail before prompting to replace the open job list. The API
            # caches the CLI probe, and select_or_create checks again for safety.
            require_basic_arkade_cli(self.api, plan)
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
        from .result_center_v0111_a2 import ResultCenterWindow
        from app.format_assessment_v0111_a2 import chosen_format_source
        dialog = ResultCenterWindow(
            job.effective_work_operations,
            display_name=job.job_id + ' - ' + job.name,
            available_jobs=self.api.report_candidates(),
            report_api=self.api,
            on_generate_report=self._a12_open_selected_report,
            format_assessment_source=chosen_format_source(self.api.settings),
        )
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
            not busy and not getattr(self, '_basic_legacy_layout', False)
            and bool(self.basic_source_path.text()) and bool(self.basic_work_path.text())
        )
        self.basic_stop_button.setEnabled(busy)
        job = None
        if self._basic_job_id:
            try:
                job = next((item for item in self.api.workspace().jobs
                            if item.job_id == self._basic_job_id), None)
            except Exception:
                job = None
        if job is None:
            self.basic_results_button.setEnabled(False)
            self.basic_progress.setValue(0)
            if self.basic_source_path.text() and self.basic_work_path.text():
                self.basic_status.setText('Klar til kontroll. Trykk Start kontroll.')
            elif self.basic_source_path.text():
                self.basic_status.setText('Velg Work-mappe for å fortsette.')
            else:
                self.basic_status.setText('Velg uttrekksmappe og Work-mappe for å begynne.')
            self.basic_run_button.setText('Start kontroll')
            return
        self.basic_progress.setValue(max(0, min(100, round(job.progress * 100))))
        self.basic_results_button.setEnabled(job.status in ('Ferdig', 'Feil', 'Hoppet over'))
        if job.status == 'Venter ved kontrollpunkt':
            self.basic_run_button.setText('Fortsett kontroll')
        elif job.status in ('Ferdig', 'Feil', 'Hoppet over'):
            self.basic_run_button.setText('Kjør kontroll på nytt')
        else:
            self.basic_run_button.setText('Start kontroll')
        text = f'{job.job_id} · {job.status} · {job.progress:.0%} fullført'
        if getattr(self, '_basic_legacy_layout', False):
            text += ' – Eksisterende Work-struktur: kjør jobben i Avansert modus.'
        if job.status == 'Ferdig':
            text += ' – Gå gjennom resultatene før faglig vurdering.'
        elif job.status == 'Feil':
            text += ' – Kontrollene må gjennomgås.'
        self.basic_status.setText(text)

    def closeEvent(self, event):
        # The old main_window.closeEvent always persists saveState(). In Basic,
        # that contains hidden docks; preserve the real advanced arrangement.
        advanced_state = self._basic_advanced_state if self._basic_active else None
        super().closeEvent(event)
        if event.isAccepted() and advanced_state is not None:
            self.config.setValue('qt/window_state', advanced_state)
            self.config.sync()
