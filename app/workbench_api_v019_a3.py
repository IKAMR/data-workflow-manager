"""v0.1.9-a3: Work/Source reconnection commands for the Qt workbench.

Existing a10/a12 workbench remains unchanged; this facade only adds explicit,
GUI-neutral read/preview/confirm operations. No GUI imports in app services.
"""
from __future__ import annotations

from app.workbench_api_v018_a3 import DwmWorkbenchAPI as _V018WorkbenchAPI
from app.job_connections_v019_a3 import (
    JobLocationHealth, SourceLinkPreview, WorkLinkPreview,
    inspect_job_locations, preview_work_link, apply_work_link,
    preview_source_link, apply_source_link,
)


class DwmWorkbenchAPI(_V018WorkbenchAPI):
    def job_location_health(self) -> tuple[JobLocationHealth, ...]:
        return inspect_job_locations(self)

    def preview_work_reconnection(self, job_id: str, folder) -> WorkLinkPreview:
        return preview_work_link(self, job_id, folder)

    def reconnect_work(self, preview: WorkLinkPreview, *, consent: bool = False):
        return apply_work_link(self, preview, consent=consent)

    def preview_source_reconnection(self, job_id: str, folder) -> SourceLinkPreview:
        return preview_source_link(self, job_id, folder)

    def reconnect_source(self, preview: SourceLinkPreview, *, consent: bool = False):
        return apply_source_link(self, preview, consent=consent)
