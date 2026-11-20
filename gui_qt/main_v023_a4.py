"""v0.2.3-a4: linear source-bound KS and safe multi-job Basic re-selection.

Never changes the shared job storage model, runner or Source/Work identity.
"""
from __future__ import annotations

from pathlib import Path

from gui_qt.main_v023_a3 import DwmMainWindow as _A3Window
from app.basic_selection_guard_v023_a4 import saved_job_decision, same_storage_path


class DwmMainWindow(_A3Window):
    def _v022_register_current(self, *, show_errors: bool = True) -> bool:
        """Avoid false Source/Work edits when the selected saved job is unchanged.

        A restored Basic view can display stale Source/Work from another job.
        Resolve only that *proven* selection drift, and never re-bind a job
        to a new path.  Real user edits still take the original guarded path.
        """
        if (not getattr(self, '_basic_active', False)
                or getattr(self, '_v022_loading_job', False)
                or getattr(self, '_v022_draft', False)
                or getattr(self, '_basic_legacy_layout', False)
                or not getattr(self, '_active_id', None)):
            return super()._v022_register_current(show_errors=show_errors)
        try:
            workspace = self.api.workspace()
            job_details = tuple(self.api.job_details(j.job_id).job for j in workspace.jobs)
            choice = saved_job_decision(
                job_details, selected_job_id=self._active_id,
                actual_active_id=getattr(workspace, 'active_job_id', None),
                source=self.basic_source_path.text().strip(),
                work=self.basic_work_path.text().strip(),
                draft=bool(getattr(self, '_v022_draft', False)),
                edited=bool(getattr(self, '_basic_selection_edited', False)),
                metadata_dirty=bool(getattr(self, '_a2_pending_dirty', False)),
            )
            if choice == 'reuse':
                # No mutation, workflow regeneration or preflight bypass: the
                # canonical job is already registered in the shared API.
                return self._v022_save_joblist_to_existing_file()
            if choice == 'restore':
                self._v022_loading_job = True
                try:
                    self._load_basic_active_job()
                finally:
                    self._v022_loading_job = False
                current = self.api.job_details(self._active_id).job
                if not (same_storage_path(self.basic_source_path.text().strip(), current.source_extraction)
                        and same_storage_path(self.basic_work_path.text().strip(),
                          getattr(current, 'effective_work_operations', None)
                          or getattr(current, 'work_operations', None))):
                    raise ValueError('Jobbvisningen kunne ikke synkroniseres med valgt Source/Work.')
                self._v022_refresh_selector(force=True)
                return self._v022_save_joblist_to_existing_file()
            if choice == 'blocked':
                raise ValueError(
                    'Jobbvalg og Source/Work stemmer ikke med lagret jobb. '
                    'Velg den aktuelle jobben på nytt. Ingen jobber eller arbeidsmapper er endret. '
                    'For bevisst endret Source/Work må «Legg til nytt uttrekk» brukes.')
        except (OSError, ValueError, RuntimeError) as exc:
            if show_errors:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, 'Kontroller valgt jobb før lagring', str(exc))
            return False
        # Registration with a deliberate user change remains strictly guarded.
        return super()._v022_register_current(show_errors=show_errors)

    def _a12_open_ks_workshop(self, _checked=False):
        from PySide6.QtWidgets import QMessageBox
        if (getattr(self, '_worker', None) is not None or self.api.running
                or getattr(self, '_job_controls_running', False)):
            QMessageBox.information(self, 'Kvalitetssikring',
                                    'Avslutt pågående jobb før du registrerer faglige vurderinger.')
            return
        if not self._active_id:
            QMessageBox.information(self, 'Kvalitetssikring', 'Velg et uttrekk i jobblisten først.')
            return
        try:
            work = getattr(self.api.job_details(self._active_id).job,
                           'effective_work_operations', None)
            if not work or not Path(work).is_dir():
                raise ValueError('Valgt jobb har ikke en tilgjengelig Work-mappe')
            from gui_qt.ks_paged_v023_a12 import KsWorkshopDialog
            KsWorkshopDialog(work, self).exec()
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kvalitetssikring',
                                'KS-grunnlaget kunne ikke åpnes. Kontroller A200–A260 '
                                'og depotrapporten.\n\n' + str(exc))

    def _basic_sync_run_plan(self):
        """Bind Basic Kjoeredetaljer to the job shown in the run/history panel.

        Batch execution changes _active_id per job, while _basic_job_id remains
        the operator's saved Basic selection.  The detached viewer follows the
        active run job; this changes presentation only, not job-list selection.
        """
        if not getattr(self, '_basic_active', False):
            return super()._basic_sync_run_plan()
        viewer = getattr(self, '_detached_run_window', None)
        tree = getattr(viewer, '_basic_plan_tree', None) if viewer is not None else None
        job_id = getattr(self, '_active_id', None)
        if tree is None or not job_id:
            return
        try:
            from app.basic_run_feedback_v0111_a3 import planned_operation_rows
            details = self.api.job_details(job_id)
            rows = planned_operation_rows(details.operations, details.job.status,
                                          details.job.current_operation)
        except (AttributeError, KeyError, RuntimeError, ValueError):
            # Never keep showing another job's operation statuses as current.
            tree.clear()
            viewer._basic_plan_key = None
            viewer.setWindowTitle('Kjøredetaljer – ' + str(job_id) + ' (status utilgjengelig)')
            return
        viewer.setWindowTitle('Kjøredetaljer – ' + str(job_id))
        # Include job identity in the cache key even when workflows are equal.
        key = (job_id, tuple((nr, name, op_id) for nr, name, _status, op_id in rows))
        if key != getattr(viewer, '_basic_plan_key', None):
            from PySide6.QtWidgets import QTreeWidgetItem
            tree.clear()
            for number, name, status, _op_id in rows:
                tree.addTopLevelItem(QTreeWidgetItem([str(number), name, status]))
            viewer._basic_plan_key = key
        else:
            for index, (_number, _name, status, _op_id) in enumerate(rows):
                item = tree.topLevelItem(index)
                if item is not None and item.text(2) != status:
                    item.setText(2, status)

    def _a9_sync_detached_run(self):
        """Keep detached title/tree on the same job as saved/live run data."""
        result = super()._a9_sync_detached_run()
        if (getattr(self, '_basic_active', False)
                and getattr(self, '_detached_run_window', None) is not None):
            self._basic_sync_run_plan()
        return result
