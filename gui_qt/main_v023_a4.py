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
