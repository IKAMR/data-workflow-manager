"""v0.2.4-a4: durable layout preferences for the run-details window.

UI/QSettings only. Inherit a3's Work-first API, run commands, job selection,
and a1's existing outer-plan splitter persistence without replacing them.
"""
from __future__ import annotations

import json

from gui_qt.main_v024_a3 import DwmMainWindow as _A3Window
from gui_qt.run_details_layout_v024_a4 import (
    history_column_widths, history_table_height, plan_table_height,
)


_COL_KEY = 'qt/v024_a4/run_history_column_widths'
_INNER_KEY = 'qt/v024_a4/run_history_log_splitter'
_OUTER_KEY = 'qt/v024/basic_details_vertical_splitter'  # v0.2.4-a1 setting


class DwmMainWindow(_A3Window):
    def _a9_float_run(self):
        """Reuse the normal independent viewer and configure its two panels."""
        result = super()._a9_float_run()
        viewer = getattr(self, '_detached_run_window', None)
        if viewer is not None and hasattr(viewer, 'history_tree'):
            self._v024_a4_bind_details(viewer)
        return result

    def _basic_add_run_plan(self, viewer):
        """Keep a1's draggable plan/history splitter, fit content if unsaved."""
        result = super()._basic_add_run_plan(viewer)
        if getattr(viewer, '_v024_plan_splitter', None) is not None:
            viewer._v024_a4_outer_had_saved = bool(self.config.value(_OUTER_KEY))
            from PySide6.QtCore import QTimer
            # a1 schedules its own one-shot restore at 0 ms. Use a single
            # subsequent 25 ms callback, so either Qt event ordering leaves
            # the content-aware default in place. A saved user setting wins.
            QTimer.singleShot(25, lambda w=viewer: self._v024_a4_fit_plan(w))
        return result

    def _v024_a4_bind_details(self, viewer):
        if getattr(viewer, '_v024_a4_bound', False):
            return
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QSplitter

        tree = viewer.history_tree
        inner = tree.parentWidget()
        if not isinstance(inner, QSplitter):
            return  # do not alter an unexpected upstream widget hierarchy
        viewer._v024_a4_bound = True
        viewer._v024_a4_ready = False
        viewer._v024_a4_restoring = False
        viewer._v024_a4_inner = inner
        inner.setChildrenCollapsible(False)
        inner.setHandleWidth(9)
        inner.splitterMoved.connect(
            lambda _pos, _index, w=viewer: self._v024_a4_store_inner(w))
        tree.header().sectionResized.connect(
            lambda _index, _old, _new, w=viewer: self._v024_a4_store_columns(w))
        # Defer until the viewer has been shown and its first history snapshot
        # is present. This uses a single Qt event-loop turn, not a timer loop.
        QTimer.singleShot(0, lambda w=viewer: self._v024_a4_initialize(w))

    def _v024_a4_initialize(self, viewer):
        if not getattr(viewer, '_v024_a4_bound', False):
            return
        viewer._v024_a4_restoring = True
        try:
            from PySide6.QtWidgets import QHeaderView

            tree = viewer.history_tree
            header = tree.header()
            # Stretch mode prevents manual resizing. All five columns stay
            # Interactive after the one-shot content-aware initialization.
            header.setStretchLastSection(False)
            header.setMinimumSectionSize(75)
            for index in range(5):
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)
            widths = history_column_widths(
                max(0, tree.viewport().width()), self.config.value(_COL_KEY))
            for index, width in enumerate(widths):
                header.resizeSection(index, width)

            inner = viewer._v024_a4_inner
            stored = self.config.value(_INNER_KEY)
            restored = False
            if stored:
                try:
                    restored = bool(inner.restoreState(stored))
                except (TypeError, ValueError, RuntimeError):
                    restored = False
            if not restored:
                self._v024_a4_fit_inner(viewer)
        except RuntimeError:
            # Native QWidget was destroyed before the queued callback ran.
            return
        finally:
            viewer._v024_a4_restoring = False
            viewer._v024_a4_ready = True

    @staticmethod
    def _v024_a4_tree_row_height(tree) -> int:
        if tree.topLevelItemCount():
            try:
                value = int(tree.sizeHintForRow(0))
                if value >= 18:
                    return value
            except (TypeError, ValueError, RuntimeError):
                pass
        return max(20, tree.fontMetrics().height() + 6)

    def _v024_a4_fit_inner(self, viewer):
        inner = getattr(viewer, '_v024_a4_inner', None)
        if inner is None:
            return
        available = inner.height()
        if available < 150:
            return  # Qt has not completed (or has too little) layout yet
        tree = viewer.history_tree
        target = history_table_height(
            available, tree.topLevelItemCount(),
            self._v024_a4_tree_row_height(tree), tree.header().height(),
        )
        inner.setSizes([target, max(0, available - target)])

    def _v024_a4_fit_plan(self, viewer):
        # A fast close/redock can destroy the native widget before the single
        # queued sizing callback. A deleted viewer is not a run failure.
        try:
            outer = getattr(viewer, '_v024_plan_splitter', None)
            tree = getattr(viewer, '_basic_plan_tree', None)
            if outer is None or tree is None:
                return
            if getattr(viewer, '_v024_a4_outer_had_saved', False):
                # The a1 handler restored the existing manual setting.
                return
            available = outer.height()
            if available < 150:
                return
            target = plan_table_height(
                available, tree.topLevelItemCount(),
                self._v024_a4_tree_row_height(tree), tree.header().height(),
            )
            outer.setSizes([target, max(0, available - target)])
            # Fit inner only for a first-time user; a saved manual divider
            # must never be modified by opening a different job.
            if not self.config.value(_INNER_KEY):
                viewer._v024_a4_restoring = True
                try:
                    self._v024_a4_fit_inner(viewer)
                finally:
                    viewer._v024_a4_restoring = False
        except RuntimeError:
            return

    def _v024_a4_store_columns(self, viewer):
        if (not getattr(viewer, '_v024_a4_ready', False)
                or getattr(viewer, '_v024_a4_restoring', False)):
            return
        header = viewer.history_tree.header()
        widths = [int(header.sectionSize(index)) for index in range(5)]
        # A transient 0px width during Qt reparent/layout is not a user edit.
        if all(width >= 75 for width in widths):
            self.config.setValue(_COL_KEY, json.dumps(widths))

    def _v024_a4_store_inner(self, viewer):
        if (not getattr(viewer, '_v024_a4_ready', False)
                or getattr(viewer, '_v024_a4_restoring', False)):
            return
        inner = getattr(viewer, '_v024_a4_inner', None)
        if inner is not None:
            self.config.setValue(_INNER_KEY, inner.saveState())

    def _a9_redock_run(self):
        """Persist preferences before the existing redock deletes its viewer."""
        viewer = getattr(self, '_detached_run_window', None)
        if viewer is not None and getattr(viewer, '_v024_a4_ready', False):
            self._v024_a4_store_columns(viewer)
            self._v024_a4_store_inner(viewer)
            self.config.sync()
        return super()._a9_redock_run()
