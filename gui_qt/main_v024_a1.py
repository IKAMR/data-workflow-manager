"""v0.2.4-a1: consistent live Basic job, real-message clock and resizable details.

UI-only extension of the existing v0.2.3 workbench. Does not select or
rewrite the persisted .n5jobs job while batch processing is in progress.
"""
from __future__ import annotations

import time

from gui_qt.main_v023_a4 import DwmMainWindow as _V023Window


class DwmMainWindow(_V023Window):
    """Presentation binding for current batch job; API remains authoritative."""

    def _v024_show_running_job(self, job_id: str) -> None:
        if not getattr(self, '_basic_active', False) or not job_id:
            return
        if job_id == getattr(self, '_basic_job_id', None) and job_id == getattr(self, '_active_id', None):
            return
        try:
            # Require the job to exist in the current list; never create or
            # retarget a saved job because of an event from a different list.
            self.api.job_details(job_id)
        except (AttributeError, KeyError, ValueError, RuntimeError):
            return
        self._active_id = job_id
        self._basic_job_id = job_id
        self._basic_last_run_signal = None
        self._basic_last_run_message = ''
        self._basic_operation_fraction = None
        self._basic_operation_index = None
        previous = bool(getattr(self, '_v022_loading_job', False))
        self._v022_loading_job = True
        try:
            # Read-only form refresh; do not call API select_job or save.
            self._load_basic_active_job()
        finally:
            self._v022_loading_job = previous
        if hasattr(self, '_v022_draft'):
            self._v022_draft = False
        self._v022_refresh_selector(force=True)
        self._a8_refresh_job_log(force=True)
        self._a8_restore_run_context(force=True)

    def _a8_process_run_event(self, event):
        kind = str(getattr(event, 'kind', '') or '')
        job_id = str(getattr(event, 'job_id', '') or '')
        if getattr(self, '_basic_active', False) and job_id:
            if kind == 'run.started':
                self._v024_show_running_job(job_id)
            elif kind in ('run.log', 'run.progress', 'run.state') and job_id != getattr(self, '_active_id', None):
                try:
                    status = str(self.api.job_details(job_id).job.status)
                except (AttributeError, KeyError, ValueError, RuntimeError):
                    status = ''
                if status in ('Kjører', 'running', 'JobStatus.RUNNING'):
                    self._v024_show_running_job(job_id)
        old_signal = getattr(self, '_basic_last_run_signal', None)
        result = super()._a8_process_run_event(event)
        # The inherited Basic observer previously reset this on run.state
        # even with no actual message. Only real start/progress/log/error
        # information should restart the clock.
        if getattr(self, '_basic_active', False) and job_id == getattr(self, '_basic_job_id', None):
            if kind == 'run.state' or (kind == 'run.progress' and not str(getattr(event, 'message', '') or '').strip()):
                self._basic_last_run_signal = old_signal
            if kind == 'run.started' and self._basic_last_run_signal is None:
                self._basic_last_run_signal = time.monotonic()
        return result

    def _basic_add_run_plan(self, viewer):
        """Put the 17-row plan and existing history/log splitter in a splitter.

        The v0.2.3 tree had a fixed 240px maximum and was inserted as a
        separate QVBoxLayout item, so there was no draggable divider.
        """
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import QSplitter, QSizePolicy

        super()._basic_add_run_plan(viewer)
        if getattr(viewer, '_v024_plan_splitter', None) is not None:
            return
        tree = getattr(viewer, '_basic_plan_tree', None)
        layout = viewer.layout()
        if tree is None or layout is None:
            return
        tree_index = layout.indexOf(tree)
        if tree_index < 0:
            return
        # Native DetachedRunWindow consists of summary, progress, (Basic
        # caption and plan), history/events splitter, and footer.
        old_splitter = None
        for index in range(tree_index + 1, layout.count()):
            item = layout.itemAt(index)
            candidate = item.widget() if item is not None else None
            if isinstance(candidate, QSplitter):
                old_splitter = candidate
                break
        if old_splitter is None:
            return
        layout.removeWidget(tree)
        layout.removeWidget(old_splitter)
        tree.setMaximumHeight(16777215)
        tree.setMinimumHeight(80)
        tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        splitter = QSplitter(Qt.Orientation.Vertical, viewer)
        splitter.setObjectName('v024_basic_details_vertical_splitter')
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(9)
        splitter.addWidget(tree)
        splitter.addWidget(old_splitter)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.insertWidget(tree_index, splitter, 1)
        viewer._v024_plan_splitter = splitter
        tree.setToolTip('Alle deljobber. Dra skillet under tabellen opp eller ned for mer plass.')
        splitter.setToolTip('Dra for å endre høyden på deljobblisten.')
        stored = self.config.value('qt/v024/basic_details_vertical_splitter')
        def initialize():
            if stored and splitter.restoreState(stored):
                return
            height = max(300, splitter.height())
            splitter.setSizes([int(height * .53), int(height * .47)])
        QTimer.singleShot(0, initialize)
        splitter.splitterMoved.connect(
            lambda _pos, _index: self.config.setValue(
                'qt/v024/basic_details_vertical_splitter', splitter.saveState()))

    def _open_basic_run_details(self):
        # The old Basic command overwrote _active_id with the stale operator
        # selection. Keep both display selectors on the actual running job.
        if getattr(self, '_basic_active', False):
            current = getattr(self, '_a8_live_job', None)
            if current and (self.api.running or getattr(self, '_worker', None) is not None):
                self._v024_show_running_job(str(current))
        return super()._open_basic_run_details()
