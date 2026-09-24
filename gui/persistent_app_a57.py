
from __future__ import annotations

from . import theme
from .persistent_app_a56 import WorkflowApp as A56WorkflowApp


class WorkflowApp(A56WorkflowApp):
    """v0.1.5-a22: New job list always contains one blank active JOB-001."""

    def _new_job_list(self) -> bool:
        created = super()._new_job_list()
        if not created:
            return False

        # Some historical layers implement "new job list" as a completely
        # empty JobBatch.  For the single-job main-window workflow we want a
        # usable blank draft immediately.  Only create it when no job exists,
        # so older layers that already create JOB-001 are not duplicated.
        if len(self.jobs) == 0:
            job = self.jobs.new_job(None)

            set_owner = getattr(job, "set_owner_identity", None)
            current_identity = getattr(self, "current_user_identity", None)
            if callable(set_owner) and callable(current_identity):
                set_owner(current_identity())

            job.profile_id = None
            self.current_job = job
        else:
            jobs = self.jobs.jobs()
            self.current_job = jobs[0] if jobs else None

        # A new list starts blank: no source and no workflow are inherited.
        self.workflow.clear()
        self.workflow_panel.refresh()
        self.source_panel.path_var.set("")
        self.source_panel.detect()

        self._refresh_active_job_label()
        self._update_run_button()
        self._refresh_effective_work_status()

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.jobs_window.refresh()
            except Exception:
                pass

        self.status_bar.set_status("Ny jobbliste - JOB-001 opprettet")
        return True


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
