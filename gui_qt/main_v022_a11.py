"""v0.2.2-a11: one-shot, data-aware Advanced workspace fitting.

The shared a10 multi-job controller, job runner, Work and evidence remain
unchanged. Qt imports are deferred so conservative headless startup tests
can still substitute a minimal window class.
"""
from __future__ import annotations

import json

from app.advanced_layout_v022_a11 import (
    plan_advanced_layout, restored_splitter_sizes, severe_panel_clipping,
)
from gui_qt.main_v022_a10 import DwmMainWindow as _A10Window


class DwmMainWindow(_A10Window):
    """Repair cramped layouts after show/data loading, not on every job click."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The old headless startup tests supply a valid fake window with no
        # toolbar. Never load QtCore/QtWidgets when working with that stand-in.
        if not hasattr(self, '_toolbar'):
            return
        self._a11_fit_queued = False
        self._a11_initial_advanced = False
        self._a11_manual_autofit = False
        self._a11_saved_layout = self.config.value(
            'qt/a11_advanced_layout_saved', False, type=bool)
        self._a11_last_content = self._a11_content_key()
        self._a11_saved_columns_restored = False
        self._a11_splitter_restored = False
        action = getattr(self, 'a10_autofit_action', None)
        if action is not None:
            action.setToolTip(
                'Fordel plass mellom Jobber, Arbeidsflyt, Kjoereloep og Systemlogg. '
                'Du kan dra delerne etterpaa; tilpasningen endrer ikke jobbdata.')
        from PySide6.QtCore import QTimer
        # The a12 dock balancer and a14 window placement run in zero-ms
        # startup callbacks. Apply ONE bounded dock-only repair afterwards.
        QTimer.singleShot(160, self._a11_initial_fit)

    def _a11_content_key(self):
        workspace = self.api.workspace()
        return (str(workspace.job_list_path or ''),
                tuple((job.job_id, str(job.name)) for job in workspace.jobs))

    def _a11_initial_fit(self):
        if not hasattr(self, '_a11_fit_queued'):
            return
        if not getattr(self, '_basic_active', False):
            self._a11_queue_fit(allow_expand=True)

    def _a11_queue_fit(self, *, allow_expand: bool = False):
        if not hasattr(self, '_a11_fit_queued') or self._a11_fit_queued:
            return
        if getattr(self, '_basic_active', False):
            return
        from PySide6.QtCore import QTimer
        self._a11_fit_queued = True
        QTimer.singleShot(0, lambda: self._a11_deferred_fit(allow_expand))

    def _a11_deferred_fit(self, allow_expand):
        self._a11_fit_queued = False
        if not getattr(self, '_basic_active', False) and self.isVisible():
            self._a11_fit_advanced(allow_expand=allow_expand)
            self._a11_initial_advanced = True

    def _refresh(self, *args, **kwargs):
        outcome = super()._refresh(*args, **kwargs)
        # Construction/worker events call _refresh too. Only a change to the
        # job list or names can schedule fitting, never job selection/progress.
        if hasattr(self, '_a11_last_content'):
            next_key = self._a11_content_key()
            if next_key != self._a11_last_content:
                old_path = self._a11_last_content[0]
                self._a11_last_content = next_key
                self._a11_queue_fit(allow_expand=old_path != next_key[0])
        return outcome

    def _leave_basic(self):
        was_basic = getattr(self, '_basic_active', False)
        result = super()._leave_basic()
        if (was_basic and hasattr(self, '_a11_initial_advanced')
                and not self._a11_initial_advanced):
            self._a11_queue_fit(allow_expand=True)
        return result

    def _a12_activity_tab_changed(self, index):
        result = super()._a12_activity_tab_changed(index)
        # The run-history splitter can be zero-sized while its tab is hidden.
        # Finish restoring its saved divider the first time Kjoereloep opens.
        if (index == 1 and hasattr(self, '_a11_splitter_restored')
                and not self._a11_splitter_restored):
            self._a11_queue_fit(allow_expand=False)
        return result

    def _a10_autofit(self):
        """Reuse the a10 menu action; explicit user request always refits."""
        if getattr(self, '_basic_active', False):
            return
        if not hasattr(self, 'dock_jobs'):
            return
        self._a11_fit_advanced(force=True, allow_expand=True)
        self._a11_manual_autofit = True
        self.statusBar().showMessage(
            'Arbeidsflaten er autojustert. Deler og kolonner kan dras manuelt.',
            6000)

    def _a11_measure_text(self, tree, column: int, default: int) -> int:
        try:
            font = tree.fontMetrics()
            values = [tree.topLevelItem(i).text(column)
                      for i in range(tree.topLevelItemCount())]
            return max([default] + [font.horizontalAdvance(v) for v in values])
        except (AttributeError, RuntimeError):
            return default

    def _a11_restore_column_preferences(self):
        if self._a11_saved_columns_restored:
            return
        self._a11_saved_columns_restored = True
        if not self._a11_saved_layout:
            return
        for tree, key in (
            (self.jobs_tree, 'qt/a11_jobs_name_column'),
            (self.workflow_tree, 'qt/a11_workflow_name_column'),
            (self.run_history_tree, 'qt/a11_history_name_column'),
        ):
            try:
                width = int(self.config.value(key, 0) or 0)
                if 140 <= width <= 680:
                    tree.setColumnWidth(1, width)
            except (TypeError, ValueError, RuntimeError):
                pass

    def _a11_set_columns(self, plan, *, forced: bool, allow_expand: bool):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QHeaderView
        for tree, desired in (
            (self.jobs_tree, plan.job_name_width),
            (self.workflow_tree, plan.workflow_name_width),
            (self.run_history_tree, plan.history_name_width),
        ):
            # A10 names are already interactive in Jobber/Arbeidsflyt; make
            # Deljobb in Kjoereloep independently draggable as well.
            header = tree.header()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            if forced or (allow_expand and not self._a11_saved_layout):
                if forced or tree.columnWidth(1) < desired - 8:
                    tree.setColumnWidth(1, desired)

    def _a11_restore_inner_splitter(self, *, forced: bool, wanted: int):
        splitter = self.run_history_splitter
        if splitter.height() < 320:
            return
        current = splitter.sizes()
        if len(current) != 2:
            return
        saved = None
        if not forced and self._a11_saved_layout:
            saved = restored_splitter_sizes(
                str(self.config.value('qt/a11_run_splitter_sizes', '') or ''),
                sum(current))
        if saved is not None:
            splitter.setSizes(list(saved))
            self._a12_run_splitter_initialized = True
        elif forced or (not self._a11_saved_layout and current[0] < wanted - 32):
            available = sum(current)
            if available >= 320:
                upper = max(140, min(wanted, available - 140))
                splitter.setSizes([upper, available - upper])
                self._a12_run_splitter_initialized = True

    def _a11_fit_advanced(self, *, force: bool = False,
                          allow_expand: bool = False):
        if getattr(self, '_basic_active', False) or not self.isVisible():
            return
        if not all(hasattr(self, n) for n in (
                'dock_jobs', 'dock_workflow', 'dock_log', 'dock_system',
                'jobs_tree', 'workflow_tree', 'run_history_tree',
                'run_history_splitter')):
            return
        from PySide6.QtCore import Qt
        jobs_visible = self.dock_jobs.isVisible() and not self.dock_jobs.isFloating()
        workflow_visible = (self.dock_workflow.isVisible()
                            and not self.dock_workflow.isFloating())
        activity_visible = self.dock_log.isVisible() and not self.dock_log.isFloating()
        system_visible = (self.dock_system.isVisible()
                          and not self.dock_system.isFloating())
        if not (jobs_visible or workflow_visible or activity_visible):
            return
        self._a11_restore_column_preferences()
        plan = plan_advanced_layout(
            self.width(), self.height(),
            job_name_px=self._a11_measure_text(self.jobs_tree, 1, 245),
            operation_name_px=self._a11_measure_text(self.workflow_tree, 1, 230),
            history_name_px=self._a11_measure_text(self.run_history_tree, 1, 230),
            job_count=self.jobs_tree.topLevelItemCount(),
            history_count=self.run_history_tree.topLevelItemCount(),
            system_visible=system_visible,
        )
        self._a11_set_columns(plan, forced=force,
                              allow_expand=allow_expand)
        # Restore deliberately saved a11 sizes; only an extremely damaged
        # panel is repaired automatically. A first a11 run may fix old cramped
        # a10 sizes, but subsequent job clicks never rearrange the docks.
        allow_panel_changes = (force or not self._a11_saved_layout)
        severe = severe_panel_clipping(
            left_width=self.dock_jobs.width() if jobs_visible else 999,
            activity_height=self.dock_log.height() if activity_visible else 999,
            activity_width=self.dock_log.width() if activity_visible else 999,
            system_width=self.dock_system.width() if system_visible else 999,
            system_visible=system_visible,
        )
        if not self._a11_splitter_restored and self.run_history_splitter.height() >= 320:
            # A saved manual internal divider is not part of QMainWindow's
            # saveState; restore it once after the child widgets are visible.
            if self._a11_saved_layout and activity_visible:
                self._a11_restore_inner_splitter(
                    forced=False, wanted=plan.history_upper_height)
            self._a11_splitter_restored = True
        if not force and not allow_expand and not severe:
            return
        may_repair = allow_panel_changes or severe
        if jobs_visible and workflow_visible and may_repair:
            left = Qt.DockWidgetArea.LeftDockWidgetArea
            if (self.dockWidgetArea(self.dock_jobs) == left
                    and self.dockWidgetArea(self.dock_workflow) == left):
                if force or self.dock_jobs.width() < plan.left_width - 26:
                    self.resizeDocks([self.dock_jobs, self.dock_workflow],
                                     [plan.left_width, plan.left_width],
                                     Qt.Orientation.Horizontal)
                # Correct a nearly collapsed jobs/workflow height, not a
                # balanced saved layout. This also leaves manual drag alone.
                total_height = self.dock_jobs.height() + self.dock_workflow.height()
                if total_height >= 440 and (force or self.dock_jobs.height() < 205
                                            or self.dock_workflow.height() < 245):
                    upper = min(max(225, plan.job_upper_height), total_height - 245)
                    self.resizeDocks([self.dock_jobs, self.dock_workflow],
                                     [upper, total_height - upper],
                                     Qt.Orientation.Vertical)
        if activity_visible and may_repair:
            bottom = Qt.DockWidgetArea.BottomDockWidgetArea
            if self.dockWidgetArea(self.dock_log) == bottom:
                if force or self.dock_log.height() < plan.activity_height - 36:
                    pair = ([self.dock_log, self.dock_system]
                            if system_visible and self.dockWidgetArea(self.dock_system) == bottom
                            else [self.dock_log])
                    self.resizeDocks(pair, [plan.activity_height] * len(pair),
                                     Qt.Orientation.Vertical)
                if system_visible and self.dockWidgetArea(self.dock_system) == bottom:
                    total_width = self.dock_log.width() + self.dock_system.width()
                    sys_min = min(plan.system_width, max(110, total_width - 320))
                    log_min = max(300, total_width - sys_min)
                    if (force or self.dock_system.width() < max(115, sys_min - 34)
                            or self.dock_log.width() < min(395, log_min - 36)):
                        self.resizeDocks(
                            [self.dock_log, self.dock_system],
                            [max(100, total_width - sys_min), sys_min],
                            Qt.Orientation.Horizontal)
                if force or not self._a11_saved_layout:
                    self._a11_restore_inner_splitter(
                        forced=force, wanted=plan.history_upper_height)

    def closeEvent(self, event):
        result = super().closeEvent(event)
        # The original base class handles job list confirmation and Qt state.
        # Persist view sizes only if closing was accepted, never change data.
        if (not hasattr(self, '_toolbar') or not event.isAccepted()
                or not hasattr(self, 'config')):
            return result
        for widget, key in (
            (self.jobs_tree, 'qt/a11_jobs_name_column'),
            (self.workflow_tree, 'qt/a11_workflow_name_column'),
            (self.run_history_tree, 'qt/a11_history_name_column'),
        ):
            self.config.setValue(key, widget.columnWidth(1))
        self.config.setValue('qt/a11_run_splitter_sizes',
                             json.dumps(self.run_history_splitter.sizes()))
        if self._a11_initial_advanced or self._a11_manual_autofit:
            self.config.setValue('qt/a11_advanced_layout_saved', True)
        self.config.sync()
        return result
