"""v0.2.5-a3: one confirmed Continue + remaining batch in both Qt modes.

Uses the existing _start_worker, per-job API, shared Work history and Stop.
No extra executor, job-list mutation, implicit reset or completed-job rerun.
"""
from __future__ import annotations

from app.batch_continue_v025_a3 import plan_remaining_jobs
from gui_qt.main_v025_a1 import DwmMainWindow as _V025A1Window


class DwmMainWindow(_V025A1Window):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._v025_a3_actions_ready = False
        # Older headless GUI startup tests use a fake window without widgets.
        if not (hasattr(self, '_toolbar') and hasattr(self, 'ready_action')
                and hasattr(self, 'a10_basic_all_button')):
            return
        self._v025_a3_install_actions()
        self._v025_a3_actions_ready = True
        self._v025_a3_update_actions()

    def _v025_a3_install_actions(self) -> None:
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QPushButton

        self.v025_a3_action = QAction('Fortsett og kjør resterende (0)', self)
        self.v025_a3_action.setObjectName('v025_a3_continue_remaining')
        self.v025_a3_action.triggered.connect(self._v025_a3_run_remaining)
        for top in self.menuBar().actions():
            menu = top.menu()
            if menu is not None and top.text().replace('&', '').strip() == 'Kjør':
                menu.insertAction(self.ready_action, self.v025_a3_action)
                break
        self._toolbar.insertAction(self.ready_action, self.v025_a3_action)

        parent = self.a10_basic_all_button.parentWidget()
        self.v025_a3_basic_button = QPushButton('Fortsett og kjør resterende (0)', parent)
        self.v025_a3_basic_button.setObjectName('v025_a3_basic_continue_remaining')
        self.v025_a3_basic_button.clicked.connect(self._v025_a3_run_remaining)
        layout = parent.layout()
        if layout is not None:
            where = layout.indexOf(self.a10_basic_all_button)
            if where >= 0 and hasattr(layout, 'insertWidget'):
                layout.insertWidget(where + 1, self.v025_a3_basic_button)
            else:
                layout.addWidget(self.v025_a3_basic_button)
        else:
            self.v025_a3_basic_button.hide()

    def _v025_a3_busy(self) -> bool:
        return bool(getattr(self, '_worker', None) is not None
                    or getattr(self.api, 'running', False)
                    or getattr(self, '_job_controls_running', False)
                    or getattr(self, '_basic_starting', False))

    def _v025_a3_plan(self):
        return plan_remaining_jobs(
            self.api.workspace().jobs,
            details_for=self.api.job_details,
            resume_for=self.api.resume_option_for_job,
        )

    def _v025_a3_update_actions(self) -> None:
        if not getattr(self, '_v025_a3_actions_ready', False):
            return
        busy = self._v025_a3_busy()
        try:
            plan = None if busy else self._v025_a3_plan()
        except (AttributeError, OSError, RuntimeError, ValueError):
            plan = None
        count = len(plan.steps) if plan is not None else 0
        label = f'Fortsett og kjør resterende ({count})'
        reason = ('Kjøringen pågår.' if busy else
                  '\n'.join(f'{item.job_id}: {item.reason}' for item in plan.blocked)
                  if plan is not None and plan.blocked else
                  'Fortsetter delvis kjørte jobber og starter nye jobber i jobblistens rekkefølge. '
                  'Fullførte jobber kjøres ikke på nytt.')
        available = bool(plan is not None and plan.runnable and not busy)
        for control in (self.v025_a3_action, self.v025_a3_basic_button):
            control.setText(label)
            control.setEnabled(available)
            control.setToolTip(reason)

    def _refresh(self, *args, **kwargs):
        result = super()._refresh(*args, **kwargs)
        self._v025_a3_update_actions()
        return result

    def _sync_basic_status(self):
        result = super()._sync_basic_status()
        self._v025_a3_update_actions()
        return result

    def _set_running_ui(self, running):
        result = super()._set_running_ui(running)
        self._v025_a3_update_actions()
        return result

    def _v025_a3_run_remaining(self, _checked=False):
        from PySide6.QtWidgets import QMessageBox

        if self._v025_a3_busy():
            return
        if (getattr(self, '_basic_active', False)
                and (getattr(self, '_v022_draft', False)
                     or getattr(self, '_basic_selection_edited', False)
                     or getattr(self, '_a2_pending_dirty', False))):
            QMessageBox.information(self, 'Jobbliste',
                                    'Lagre eller fullfør endringene i Enkel modus før samlet kjøring.')
            return
        try:
            workspace = self.api.workspace()
            plan = self._v025_a3_plan()
        except (AttributeError, OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, 'Fortsett og kjør resterende', str(exc))
            return
        if plan.blocked:
            QMessageBox.warning(
                self, 'Jobblisten har uavklarte jobber',
                '\n'.join(f'{item.job_id}: {item.reason}' for item in plan.blocked)
                + '\n\nIngen jobber er startet.')
            return
        if not plan.steps:
            QMessageBox.information(self, 'Fortsett og kjør resterende',
                                    'Ingen gjenstående jobber kan kjøres.')
            return
        lines = [step.description for step in plan.steps[:30]]
        if len(plan.steps) > len(lines):
            lines.append(f'... og {len(plan.steps) - len(lines)} flere')
        answer = QMessageBox.question(
            self, 'Fortsett og kjør resterende',
            f'Kjøre {len(plan.steps)} jobber i lagret jobblisterekkefølge?\n\n'
            + '\n'.join(lines)
            + f'\n\n{len(plan.completed)} allerede fullførte jobber hoppes over.'
            + '\nTidligere fullførte deljobber, Siegfried-resultater og Work-historikk beholdes.'
            + '\nNeste jobb starter bare når forrige jobb er fullført.'
            + '\nSekvensen stopper ved feil, avbrudd eller kontrollpunkt.'
            + '\nIngen nullstilling eller omkjøring av ferdige jobber.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes or self._v025_a3_busy():
            return
        try:
            latest = self._v025_a3_plan()
            same_list = self.api.workspace().job_list_path == workspace.job_list_path
        except (AttributeError, OSError, RuntimeError, ValueError):
            latest, same_list = None, False
        if not same_list or latest != plan or not latest.runnable:
            QMessageBox.warning(self, 'Jobblisten er endret',
                                'Kontroller jobblisten på nytt. Ingen kjøring er startet.')
            return
        # One shared worker dispatches every target in order. Continue is
        # explicit, and only fresh 0% jobs receive the ordinary Run flag.
        return self._start_worker(plan.targets)

    def _start_worker(self, jobs, *, request_id=None):
        """Existing sequential worker, with a strict completed-job boundary.

        Keep the stop-on-checkpoint change local to the a3 subclass instead of
        replacing the large legacy main_window.py in a delta package.
        """
        from queue import Queue
        from threading import Thread
        from PySide6.QtWidgets import QMessageBox
        from app.batch_continue_v025_a3 import batch_can_advance
        if len(jobs) <= 1 or not hasattr(self, '_a9_trace_run'):
            return super()._start_worker(jobs, request_id=request_id) if request_id is not None else super()._start_worker(jobs)
        from gui_qt.main_window import new_request_id
        request_id = request_id or new_request_id()
        first_job = jobs[0][0] if jobs else None
        self._a9_trace_run('ui.preflight_started', request_id, job_id=first_job,
                           run_count=len(jobs))
        warning_approvals = self._review_preflight(tuple(job_id for job_id, _rerun, _cont in jobs))
        if warning_approvals is None:
            self._a9_trace_run('ui.preflight_cancelled', request_id, job_id=first_job)
            return
        self._a9_trace_run('ui.preflight_approved', request_id, job_id=first_job)
        if not self.api.workspace().job_list_path or self.api.dirty:
            if not self._save():
                self._a9_trace_run('ui.save_cancelled', request_id, job_id=first_job)
                return
        issues = self.api.check_storage()
        if issues:
            self._a9_trace_run('ui.storage_blocked', request_id, job_id=first_job,
                               reason='; '.join(issues)[:800])
            QMessageBox.warning(self, 'Lagringskontroll', '\n'.join(issues))
            return
        present = {job.job_id for job in self.api.workspace().jobs}
        if any(job_id not in present for job_id, _rerun, _cont in jobs):
            self._a9_trace_run('ui.selection_changed', request_id, job_id=first_job,
                               reason='job_not_in_current_list')
            QMessageBox.warning(self, 'Jobbliste endret',
                                'Jobblisten er endret under klargjøring. Start kontrollen på nytt.')
            return
        self._batch_stop.clear()
        self._worker_messages = Queue()
        self._set_running_ui(True)
        self._append_log(f'Starter kjøring av {len(jobs)} jobb(er). Forespørsel: {request_id}')
        self._a9_trace_run('ui.worker_queued', request_id, job_id=first_job,
                           run_count=len(jobs))
        joblist = self.api.workspace().job_list_path or '(ikke lagret)'
        audit = self._run_audit

        def run():
            audit.record('worker.started', request_id=request_id,
                         joblist=joblist, job_id=first_job or '', run_count=len(jobs))
            job_id = first_job
            try:
                for job_id, allow_rerun, continuing in jobs:
                    if self._batch_stop.is_set():
                        audit.record('worker.cancelled', request_id=request_id,
                                     joblist=joblist, job_id=job_id)
                        break
                    self._worker_messages.put(('selected', job_id))
                    audit.record('api.run_job_called', request_id=request_id,
                                 joblist=joblist, job_id=job_id,
                                 reason='rerun' if allow_rerun else 'continue' if continuing else 'first_run')
                    ok = self.api.run_job(
                        job_id, allow_rerun=allow_rerun,
                        continue_waiting=continuing,
                        acknowledge_warnings=job_id in warning_approvals,
                    )
                    state = next((j for j in self.api.workspace().jobs if j.job_id == job_id), None)
                    audit.record('api.run_job_returned', request_id=request_id,
                                 joblist=joblist, job_id=job_id, result=bool(ok),
                                 status=state.status if state else 'unknown')
                    if not ok:
                        self._worker_messages.put(('info', f'{job_id}: Stoppet ved feil/avbrudd.'))
                        break
                    if not batch_can_advance(ok, state.status if state else None):
                        current = state.status if state else 'ukjent'
                        self._worker_messages.put((
                            'info', f'{job_id}: Ikke fullført ({current}). Resterende jobber stanset.'))
                        break
            except Exception as exc:
                audit.record('api.run_job_exception', request_id=request_id,
                             joblist=joblist, job_id=job_id if jobs else '',
                             reason=type(exc).__name__)
                self._worker_messages.put(('error', str(exc)))
            finally:
                audit.record('worker.finished', request_id=request_id,
                             joblist=joblist, job_id=first_job or '')
                self._worker_messages.put(('done', 'Kjøringen er avsluttet.'))

        self._worker = Thread(target=run, name='dwm-qt-runner', daemon=True)
        self._worker.start()
