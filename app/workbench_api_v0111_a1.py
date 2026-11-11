"""Basic's explicit Work selection on top of the stable v0.1.10 API.

No settings mutation, no directory creation and no change to existing Work
references. The selected-path layout is stored with the Job, not globally.
"""
from __future__ import annotations

from pathlib import Path

from app.application_api import DwmApiError
from app.work_output_layout import (
    DWM_WORK_LAYOUT_PARAM, effective_work_operations,
)
from app.workbench_api_v0110_a1 import DwmWorkbenchAPI as _PreviousWorkbenchAPI


class DwmWorkbenchAPI(_PreviousWorkbenchAPI):
    def use_selected_work_directly(self, job_id: str) -> None:
        """Opt a *new*, unprovisioned Basic job into direct selected Work.

        Work stores and completed jobs are never silently migrated, and the
        existing app folder/job list rule still govern every other job.
        """
        with self._guard:
            self._assert_idle()
            if job_id in self._work_references:
                raise DwmApiError(
                    'Eksisterende Work-historikk kan ikke endres. Bruk Avansert modus.'
                )
            job = self._require_job(job_id)
            work = job.work_operations
            source = job.source_extraction
            if work is None or source is None or not Path(work).is_absolute():
                raise DwmApiError('Basic krever en gyldig Source og absolutt Work-mappe.')
            if Path(job.work_root or work) != Path(work):
                raise DwmApiError('Basic krever at valgt Work brukes direkte, uten ekstra nivåer.')
            if not Path(work).is_dir():
                raise DwmApiError('Den valgte Work-mappen må eksistere.')
            if (Path(work).resolve(strict=False) == Path(source).resolve(strict=False)
                    or Path(work).resolve(strict=False) in Path(source).resolve(strict=False).parents
                    or Path(source).resolve(strict=False) in Path(work).resolve(strict=False).parents):
                raise DwmApiError('Work og Source må være adskilt.')
            # A previously used Work cannot be repurposed as a different job.
            if (Path(work) / 'job.json').exists():
                raise DwmApiError('Work-mappen inneholder allerede job.json. Åpne den eksisterende jobben i Avansert modus.')
            for position, other in enumerate(self._batch.jobs(), 1):
                if other.job_id == job_id:
                    continue
                effective = (self._work_references[other.job_id].parent
                             if other.job_id in self._work_references
                             else effective_work_operations(
                                 other.work_operations,
                                 str(self.settings.get('app_work_subfolder', 'dwm') or ''),
                                 self.output_subfolder_rule, other, position,
                             ))
                if effective is not None and Path(effective).resolve(strict=False) == Path(work).resolve(strict=False):
                    raise DwmApiError('En annen jobb bruker allerede den valgte Work-mappen.')
            job.set_operation_params(DWM_WORK_LAYOUT_PARAM, {'mode': 'selected'})
            self._dirty = True
        self._emit('job.storage_changed', job)
