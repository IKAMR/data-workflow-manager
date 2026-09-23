
from __future__ import annotations

from . import theme
from .persistent_app_a51 import WorkflowApp as A51WorkflowApp


class WorkflowApp(A51WorkflowApp):
    """v0.1.5-a17: unique Arkade aggregates and visible effective Work path."""

    def __init__(self) -> None:
        super().__init__()
        self._refresh_effective_work_status()

    def _refresh_effective_work_status(self) -> None:
        job = self.current_job
        if job is None:
            self.status_bar.set_work_operations(None, None)
            return

        base = getattr(job, "work_operations", None)
        effective = (
            getattr(job, "_effective_work_operations", None)
            or base
        )
        self.status_bar.set_work_operations(base, effective)

    def _refresh_active_job_label(self) -> None:
        super()._refresh_active_job_label()
        if hasattr(self, "status_bar"):
            self._refresh_effective_work_status()

    def _apply_effective_work_operations(self, job) -> None:
        super()._apply_effective_work_operations(job)
        if job is self.current_job and hasattr(self, "status_bar"):
            self._refresh_effective_work_status()

    def _set_output_subfolder_rule(self, rule: str) -> tuple[bool, str]:
        result = super()._set_output_subfolder_rule(rule)
        self._refresh_effective_work_status()
        return result

    def _load_job_list_file(self, path, *, show_error: bool) -> bool:
        loaded = super()._load_job_list_file(path, show_error=show_error)
        if loaded:
            self._refresh_effective_work_status()
        return loaded

    def _new_job_list(self) -> bool:
        created = super()._new_job_list()
        if created:
            self._refresh_effective_work_status()
        return created

    def _open_job(self, job) -> None:
        super()._open_job(job)
        self._refresh_effective_work_status()


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
