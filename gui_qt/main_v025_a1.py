"""v0.2.5-a1: switching Basic/Advanced during a live run is view-only.

The existing v0.2.4 runner, shared job list, Work storage and user-controlled
Stop action are retained. Only the presentation transition is changed.
"""
from __future__ import annotations

from gui_qt.main_v024_a4 import DwmMainWindow as _V024Window


_RUNNING_STATUSES = {'Kjører', 'running', 'JobStatus.RUNNING'}


class DwmMainWindow(_V024Window):
    def _v025_run_is_active(self) -> bool:
        return bool(
            getattr(self, '_worker', None) is not None
            or getattr(self.api, 'running', False)
            or getattr(self, '_job_controls_running', False)
        )

    def _v025_known_job(self, job_id: str) -> bool:
        if not job_id:
            return False
        try:
            return any(str(job.job_id) == str(job_id)
                       for job in self.api.workspace().jobs)
        except (AttributeError, RuntimeError, ValueError):
            return False

    def _v025_remember_run_event(self, event) -> None:
        kind = str(getattr(event, 'kind', '') or '')
        job_id = str(getattr(event, 'job_id', '') or '')
        if kind in ('run.finished', 'run.error', 'subjob.finished', 'subjob.error'):
            if getattr(self, '_v025_live_job', None) == job_id:
                self._v025_live_job = None
            return
        if kind not in ('run.started', 'subjob.started', 'run.progress',
                        'run.state', 'subjob.progress'):
            return
        if not self._v025_run_is_active() or not self._v025_known_job(job_id):
            return
        try:
            state = str(self.api.job_details(job_id).job.status)
        except (AttributeError, KeyError, RuntimeError, ValueError):
            state = ''
        if kind in ('run.started', 'subjob.started') or state in _RUNNING_STATUSES:
            self._v025_live_job = job_id
            # The existing Advanced runner only updates its run panel for the
            # selected job ID. Follow a newly started batch job in the *view*
            # without calling api.select_job() or changing .n5jobs / Work.
            if kind in ('run.started', 'subjob.started') and not getattr(self, '_basic_active', False):
                if getattr(self, '_active_id', None) != job_id:
                    self._active_id = job_id
                    self._refresh(force=True)

    def _a8_process_run_event(self, event):
        self._v025_remember_run_event(event)
        return super()._a8_process_run_event(event)

    def _a9_process_subjob_event(self, event):
        self._v025_remember_run_event(event)
        return super()._a9_process_subjob_event(event)

    def _v025_current_running_job(self) -> str | None:
        try:
            jobs = tuple(self.api.workspace().jobs)
        except (AttributeError, RuntimeError, ValueError):
            return None
        running = {
            str(job.job_id) for job in jobs
            if str(getattr(job, 'status', '')) in _RUNNING_STATUSES
        }
        # Prefer the most recent run event, but do not display a stale job
        # after a batch switches to another running job.
        for candidate in (getattr(self, '_v025_live_job', None),
                          getattr(self, '_a8_live_job', None)):
            if candidate and str(candidate) in running:
                return str(candidate)
        if running:
            return next((str(j.job_id) for j in jobs if str(j.job_id) in running), None)
        return None

    def _enter_basic(self):
        was_basic = bool(getattr(self, '_basic_active', False))
        result = super()._enter_basic()
        if not was_basic and self._v025_run_is_active():
            # Entering Basic while the operation is already running must not
            # depend on receiving another 'run.started' Qt signal.
            live_job = self._v025_current_running_job()
            if live_job:
                self._v024_show_running_job(live_job)
            self._sync_basic_status()
        return result

    def _leave_basic(self):
        if not getattr(self, '_basic_active', False):
            return
        if not self._v025_run_is_active():
            # Idle changes still use all the existing draft/metadata guards.
            return super()._leave_basic()

        # v0.2.4's multijob _leave_basic always invoked _v022_register_current,
        # which refuses to save while the runner is active. Navigation is NOT
        # a request to save, register, reselect or regenerate a running job.
        # Use the original view-only Qt transition. No worker or job data is
        # touched, and Basic's source/work form survives a round trip.
        from gui_qt.basic_main_v0111_a1 import DwmMainWindow as _OriginalBasic
        result = _OriginalBasic._leave_basic(self)
        if (not getattr(self, '_a11_initial_advanced', True)
                and callable(getattr(self, '_a11_queue_fit', None))):
            self._a11_queue_fit(allow_expand=True)
        return result
