"""v0.2.0-a2 shared Setup plus a7 dependency-checked job workflows."""
from __future__ import annotations

from typing import Mapping, Iterable

from app.application_api import DwmApiError
from app.ui_start_preferences_v020_a2 import UI_SETUP_KEYS, validate_ui_preferences
from app.workbench_api_v0111_a2 import DwmWorkbenchAPI as _PreviousWorkbenchAPI
from settings import save_config


class DwmWorkbenchAPI(_PreviousWorkbenchAPI):
    def set_workflow(self, job_id: str, operation_ids: Iterable[str]):
        """Validate sequence before changing cursor, Work or job-list state."""
        from app.workflow_dependencies_v022_a7 import validate_dependencies
        ids = tuple(str(value) for value in operation_ids)
        failures = validate_dependencies(ids)
        if failures:
            raise DwmApiError('Ugyldige avhengigheter i arbeidsflyten: ' + ' | '.join(failures))
        return super().set_workflow(job_id, ids)

    def prepare_a7_postprocessing(self, job_id: str):
        """Explicitly extend a saved job; resume AFTER completed technical tests.

        Historical execution and findings are never silently recategorized.
        A completed job becomes READY with a cursor at the FIRST a7
        postprocessing task. An unrun draft simply gets the new sequence.
        Failed, running, waiting, or partially run jobs require manual review.
        """
        from app.workflow_dependencies_v022_a7 import (
            ensure_a7_processing, validate_dependencies, AFTER_TESTS,
        )
        from noark5_workflow.core.job import JobStatus
        with self._guard:
            self._assert_idle()
            if job_id in self._unavailable_work_ids:
                raise DwmApiError('Work er frakoblet. Kan ikke endre arbeidsflyten.')
            job = self._require_job(job_id)
            old = tuple(job.workflow_ids)
            proposed = ensure_a7_processing(old)
            if proposed == old:
                raise DwmApiError('Ingen a7-etterbehandling a legge til for denne jobben.')
            if job_id not in self._work_references:
                raise DwmApiError('Jobben maa ha autoritativ Work-jobb for a7-etterbehandling.')
            issues = validate_dependencies(proposed)
            if issues:
                raise DwmApiError('; '.join(issues))
            completed = (job.status == JobStatus.OK and
                         job.next_operation_index == len(old))
            fresh = (job.status == JobStatus.READY and
                     job.next_operation_index == 0 and
                     float(job.progress or 0) == 0)
            if not (completed or fresh):
                raise DwmApiError('Kun fullfort jobb eller helt ny, ikke-kjort jobb kan oppgraderes automatisk.')
            previous = (old, job.status, job.next_operation_index,
                        job.progress, job.message)
            job.set_workflow(proposed)
            if completed:
                technical = [oid for oid in proposed if oid not in AFTER_TESTS]
                job.next_operation_index = len(technical)
                job.progress = len(technical) / len(proposed)
                job.status = JobStatus.READY
                job.message = 'a7: tekniske kontroller bevart; etterbehandling venter'
            else:
                job.message = 'a7-arbeidsflyt klargjort, ingen kontroller kjort'
            self._dirty = True
            try:
                self._persist_work_event(job, 'workflow.a7_prepared', job.message)
            except Exception:
                job.workflow_ids = list(previous[0])
                job.status, job.next_operation_index, job.progress, job.message = previous[1:]
                raise
        self._emit('job.workflow_changed', job)
        return self.job_details(job_id)

    def save_setup(self, changes: Mapping[str, object]) -> dict:
        """Persist new run-profile settings through the same guarded Setup API.

        The old Setup API accepts only its historical keys, and would turn
        profile arrays into strings. Split off the two typed profile keys,
        validate the COMPLETE proposed collection first, then save in the
        existing Setup Save transaction. Existing job lists are untouched.
        """
        from app.run_profiles_v022_a9 import staged_profile_settings_valid

        profile_keys = {'noark5_default_run_profile', 'noark5_custom_run_profiles'}
        profiles = {key: value for key, value in changes.items()
                    if key in profile_keys}
        ui_changes = {key: value for key, value in changes.items()
                      if key in UI_SETUP_KEYS}
        if not ui_changes and not profiles:
            return super().save_setup(changes)
        try:
            validated_ui = validate_ui_preferences(ui_changes) if ui_changes else {}
            if profiles:
                staged_profile_settings_valid({**self.settings, **profiles})
        except ValueError as exc:
            raise DwmApiError(str(exc)) from exc
        ordinary = {key: value for key, value in changes.items()
                    if key not in UI_SETUP_KEYS and key not in profile_keys}
        if ordinary:
            super().save_setup(ordinary)
        update = {**validated_ui, **profiles}
        with self._guard:
            self._assert_idle()
            saved = save_config(update)
            self.settings.update(update)
        self._emit('setup.changed', message='Oppstart, kjøreprofil og Setup lagret')
        return dict(saved)
