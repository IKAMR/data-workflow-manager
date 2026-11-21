"""v0.2.4-a3: persisted run state must not appear as an unsaved job list.

The existing Work-first implementation writes the authoritative job and the
.n5jobs index at every run state. A successful index write must also clear the
in-memory dirty marker; otherwise the GUI can display an incorrect '*' even
though a save already completed.  No extra filesystem scan or GUI-thread save.
"""
from __future__ import annotations

from app.workbench_api_v024_a2 import DwmWorkbenchAPI as _A2WorkbenchAPI


class DwmWorkbenchAPI(_A2WorkbenchAPI):
    def _persist_updated_job(self, job, active_job_id):
        # Super writes authoritative Work first, then the .n5jobs index.
        # If Work persistence raises, the exception is preserved unchanged.
        super()._persist_updated_job(job, active_job_id)
        if (self._path is not None
                and job.job_id in self._work_references
                and not getattr(self, '_work_index_warning', '')):
            # A running user cannot edit the job list; the persisted snapshot
            # includes all jobs, not only the currently executing one.
            self._dirty = False
