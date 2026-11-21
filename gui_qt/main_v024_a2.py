"""v0.2.4-a2: one Continue and Reset contract across Basic and Advanced.

All actions target the chosen job ID; no hidden API select_job, job-list
replacement, synthetic checkpoint or separate execution thread is created.
The inherited worker still performs normal storage preflight/consent.
"""
from __future__ import annotations

from app.job_run_actions_v024_a2 import can_reset, resume_option
from gui_qt.main_v024_a1 import DwmMainWindow as _A1Window


class DwmMainWindow(_A1Window):
    def __init__(self, api):
        super().__init__(api)
        self._v024_a2_actions_ready = False
        # Headless legacy GUI startup tests use minimal stand-in windows.
        # Never import QtWidgets or QtGui at module import time.
        if not (hasattr(self, 'menuBar') and hasattr(self, 'continue_action')
                and hasattr(self, 'basic_run_button')):
            return
        self._v024_a2_install_actions()
        self._v024_a2_actions_ready = True
        self._v024_a2_update_actions()

    def _v024_a2_install_actions(self):
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QHBoxLayout, QPushButton

        self.continue_action.setText('Fortsett jobb')
        self.overview_continue.setText('Fortsett jobb')
        self.reset_action = QAction('Nullstill jobb', self)
        self.reset_action.setObjectName('v024_a2_reset_job_action')
        self.reset_action.triggered.connect(self._v024_a2_reset_job)
        # Existing Kjor menu and toolbar stay in place; add one action only.
        for action in self.menuBar().actions():
            menu = action.menu()
            if menu is not None and action.text().replace('&', '').strip() == 'Kj\u00f8r':
                menu.insertAction(self.ready_action, self.reset_action)
                break
        if hasattr(self, '_toolbar'):
            self._toolbar.insertAction(self.stop_action, self.reset_action)

        # Overview uses its existing horizontal command row.
        self.overview_reset = QPushButton('Nullstill jobb', self.overview_continue.parentWidget())
        self.overview_reset.setObjectName('v024_a2_overview_reset_job')
        self.overview_reset.clicked.connect(self._v024_a2_reset_job)
        page_layout = self.overview_continue.parentWidget().layout()
        inserted = False
        if page_layout is not None:
            for i in range(page_layout.count()):
                sub = page_layout.itemAt(i).layout()
                if sub is not None and sub.indexOf(self.overview_continue) >= 0:
                    sub.insertWidget(sub.indexOf(self.overview_continue) + 1, self.overview_reset)
                    inserted = True
                    break
        if not inserted:
            self.overview_reset.hide()

        # Basic: a separate compact row prevents the main run row from
        # overflowing on laptops (Start/Stop/Log/Results stay unchanged).
        self.basic_continue_button = QPushButton('Fortsett jobb', self.basic_run_button.parentWidget())
        self.basic_continue_button.setObjectName('v024_a2_basic_continue_job')
        self.basic_continue_button.clicked.connect(self._continue_job)
        self.basic_reset_button = QPushButton('Nullstill jobb', self.basic_run_button.parentWidget())
        self.basic_reset_button.setObjectName('v024_a2_basic_reset_job')
        self.basic_reset_button.clicked.connect(self._v024_a2_reset_job)
        run_layout = self.basic_run_button.parentWidget().layout()
        inserted = False
        if run_layout is not None:
            for i in range(run_layout.count()):
                row = run_layout.itemAt(i).layout()
                if row is not None and row.indexOf(self.basic_run_button) >= 0:
                    controls = QHBoxLayout()
                    controls.addWidget(self.basic_continue_button)
                    controls.addWidget(self.basic_reset_button)
                    controls.addStretch(1)
                    run_layout.insertLayout(i + 1, controls)
                    inserted = True
                    break
        if not inserted:
            self.basic_continue_button.hide()
            self.basic_reset_button.hide()

    def _v024_a2_selected(self):
        job_id = str(getattr(self, '_active_id', '') or '')
        if not job_id:
            return None, None
        if getattr(self, '_basic_active', False):
            if (getattr(self, '_v022_draft', False)
                    or getattr(self, '_basic_job_id', None) != job_id
                    or getattr(self, '_basic_selection_edited', False)):
                return None, None
        try:
            details = self.api.job_details(job_id)
        except (AttributeError, KeyError, ValueError, RuntimeError):
            return None, None
        cursor = details.job.current_operation
        previous_checkpoint = bool(0 < cursor <= len(details.operations)
                                   and details.operations[cursor - 1].checkpoint)
        option = resume_option(status=details.job.status,
                               cursor=cursor,
                               total=details.job.operation_count,
                               previous_checkpoint=previous_checkpoint,
                               message=details.message)
        api_policy = getattr(self.api, 'resume_option_for_job', None)
        if callable(api_policy):
            try:
                option = api_policy(job_id)
            except (AttributeError, KeyError, ValueError, RuntimeError):
                return None, None
        return details, option

    def _v024_a2_update_actions(self):
        if not getattr(self, '_v024_a2_actions_ready', False):
            return
        details, option = self._v024_a2_selected()
        busy = bool(getattr(self, '_worker', None) is not None or self.api.running
                    or getattr(self, '_job_controls_running', False)
                    or getattr(self, '_basic_starting', False))
        can_continue = bool(details and option.allowed and not busy)
        can_restart = bool(details and not busy and can_reset(
            status=details.job.status,
            cursor=details.job.current_operation,
            progress=details.job.progress))
        explanation = (f'Fortsett fra deljobb {option.position} av {option.total}; '
                       'beholder tidligere fullf\u00f8rte deljobber og Work-historikk.'
                       if can_continue else (option.reason if option else 'Velg en registrert jobb.'))
        reset_help = ('Nullstiller kun status, fremdrift og kj\u00f8remark\u00f8r for valgt jobb. '
                      'Source, Work, resultater og historikk beholdes.')
        for control in (self.continue_action, self.overview_continue,
                        self.basic_continue_button):
            control.setEnabled(can_continue)
            control.setToolTip(explanation)
        for control in (self.reset_action, self.overview_reset,
                        self.basic_reset_button):
            control.setEnabled(can_restart)
            control.setToolTip(reset_help)
        if can_continue:
            # For partial/failed jobs a regular rerun would clear the cursor.
            # Require an explicit Continue or Reset instead.
            self.run_action.setEnabled(False)
            self.overview_run.setEnabled(False)
            self.run_action.setToolTip('Bruk Fortsett jobb, eller Nullstill jobb for \u00e5 kj\u00f8re fra start.')
            self.overview_run.setToolTip(self.run_action.toolTip())
            self.basic_run_button.setEnabled(False)
            self.basic_run_button.setToolTip('Bruk Fortsett jobb, eller Nullstill jobb for \u00e5 starte fra deljobb 1.')
        else:
            self.run_action.setToolTip('Kj\u00f8r valgt jobb')
            self.overview_run.setToolTip('Kj\u00f8r valgt jobb')
            self.basic_run_button.setToolTip('Start eller kj\u00f8r kontrollen p\u00e5 nytt')

    def _refresh(self, *args, **kwargs):
        result = super()._refresh(*args, **kwargs)
        if getattr(self, '_v024_a2_actions_ready', False):
            self._v024_a2_update_actions()
        return result

    def _sync_basic_status(self):
        result = super()._sync_basic_status()
        if getattr(self, '_v024_a2_actions_ready', False):
            self._v024_a2_update_actions()
        return result

    def _set_running_ui(self, running):
        result = super()._set_running_ui(running)
        if getattr(self, '_v024_a2_actions_ready', False):
            self._v024_a2_update_actions()
        return result

    def _start_basic_control(self):
        # Basic's old button would call Run for a FAILED job, causing a full
        # rerun. If it is invoked by keyboard/automation despite being
        # disabled, route it to the same explicit Continue action instead.
        if getattr(self, '_basic_active', False):
            details, option = self._v024_a2_selected()
            if details and option.allowed:
                return self._continue_job()
        return super()._start_basic_control()

    def _v024_a2_save_pending_metadata(self) -> bool:
        if not (getattr(self, '_basic_active', False)
                and getattr(self, '_a2_pending_dirty', False)):
            return True
        from PySide6.QtWidgets import QMessageBox
        job = self._a2_matching_job()
        if job is None:
            QMessageBox.warning(self, 'Fortsett', 'DIAS-metadata er ikke knyttet til valgt jobb.')
            return False
        try:
            self._a2_save_metadata(job)
            return True
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Fortsett', str(exc))
            return False

    def _continue_job(self, _checked=False):
        from PySide6.QtWidgets import QMessageBox
        if (getattr(self, '_worker', None) is not None or self.api.running
                or getattr(self, '_job_controls_running', False)):
            return
        details, option = self._v024_a2_selected()
        if not details or not option.allowed:
            QMessageBox.information(self, 'Fortsett jobb',
                                    option.reason if option else 'Velg en registrert jobb.')
            return
        if option.mode == 'checkpoint':
            # Inherited path retains the original checkpoint contract and
            # Basic DIAS handling; the new API handles this mode unchanged.
            return super()._continue_job()
        if not self._v024_a2_save_pending_metadata():
            return
        job_id = details.job.job_id
        action = 'feilede deljobben' if option.mode == 'failed_operation' else 'neste deljobb'
        answer = QMessageBox.question(
            self, 'Fortsett jobb',
            f'Fortsette {job_id} fra deljobb {option.position} av {option.total}?\n\n'
            f'DWM kj\u00f8rer {action} og resten av arbeidsflyten. Tidligere '
            'fullf\u00f8rte deljobber, Source og lagrede Work-resultater beholdes.\n\n'
            'Dette er IKKE en nullstilling eller en ny kj\u00f8ring fra start.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._append_log(f'{job_id}: Fortsettelse bestilt fra deljobb {option.position}/{option.total}.')
        # continue_waiting=True signifies the operator's explicit Continue
        # command; the a2 API distinguishes failed/READY from checkpoints.
        return self._start_worker([(job_id, False, True)])

    def _v024_a2_reset_job(self, _checked=False):
        from PySide6.QtWidgets import QMessageBox
        if (getattr(self, '_worker', None) is not None or self.api.running
                or getattr(self, '_job_controls_running', False)):
            return
        details, _option = self._v024_a2_selected()
        if not details or not can_reset(status=details.job.status,
                                        cursor=details.job.current_operation,
                                        progress=details.job.progress):
            QMessageBox.information(self, 'Nullstill jobb',
                                    'Velg en registrert jobb med tidligere kj\u00f8restatus.')
            return
        job_id = details.job.job_id
        answer = QMessageBox.question(
            self, 'Nullstill jobb',
            f'Nullstille {job_id} til deljobb 1 av {details.job.operation_count}?\n\n'
            'Dette setter kj\u00f8remark\u00f8ren og fremdriften til null og '
            'gj\u00f8r jobben klar for en NY kj\u00f8ring fra start.\n\n'
            'Originale Source-filer, eksisterende Work-resultater, logg og '
            'historikk slettes IKKE.\n\nNullstill denne jobben?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.reset_job_execution(job_id)
        except (OSError, ValueError, RuntimeError) as exc:
            self._error(exc)
            return
        self._basic_last_run_signal = None
        self._basic_last_run_message = ''
        self._basic_operation_index = None
        self._basic_operation_fraction = None
        self._append_log(f'{job_id}: Jobbstatus nullstilt. Historiske Work-resultater er beholdt.')
        self._refresh(force=True)
        self._a8_restore_run_context(force=True)
        self._a8_refresh_job_log(force=True)
        if getattr(self, '_basic_active', False):
            self._sync_basic_status()
        warning = str(getattr(self.api, '_v024_a2_reset_index_warning', '') or '')
        if warning:
            QMessageBox.warning(self, 'Jobb nullstilt i Work', warning)
