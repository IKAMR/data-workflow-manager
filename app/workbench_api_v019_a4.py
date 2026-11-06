"""v0.1.9-a4: add explicit multi-job, root-relative storage relocation.

The existing a3 single-job reconnection commands and all DWM execution,
reporting and Work history continue to use their established APIs.
"""
from __future__ import annotations

from app.workbench_api_v019_a3 import DwmWorkbenchAPI as _A3WorkbenchAPI
from app.storage_portability_v019_a4 import (
    RootRebasePlan, apply_root_rebase, preview_root_rebase,
)


class DwmWorkbenchAPI(_A3WorkbenchAPI):
    def preview_storage_root_rebase(self, old_root, new_root) -> RootRebasePlan:
        return preview_root_rebase(self, old_root, new_root)

    def rebase_storage_root(self, plan: RootRebasePlan, *, consent: bool = False) -> tuple[str, ...]:
        return apply_root_rebase(self, plan, consent=consent)
