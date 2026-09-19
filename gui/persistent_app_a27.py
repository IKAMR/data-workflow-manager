from __future__ import annotations

from pathlib import Path

from . import theme
from .persistent_app_a26 import WorkflowApp as A26WorkflowApp


class WorkflowApp(A26WorkflowApp):
    """a15.11: make the first single-job workflow start directly from Source.

    Only an entirely empty in-memory job list may create JOB-001 implicitly.
    Once any job exists, changing Source never creates another job.
    """

    def _ensure_job_for_current_source(self):
        root = self.source_panel.path_var.get().strip()
        if not root:
            return self.current_job

        path = Path(root)

        # Normal case: Source belongs to the already active job.
        if self.current_job is not None:
            self.current_job.source_extraction = path
            self._refresh_active_job_label()
            return self.current_job

        # If there is no active job, first reuse an existing job with this
        # extraction. This preserves the established "never duplicate by Source"
        # contract.
        existing = next(
            (
                job
                for job in self.jobs.jobs()
                if job.active_extraction_root == path
            ),
            None,
        )
        if existing is not None:
            self.current_job = existing
            self._apply_profile(existing.profile_id, persist=False)
            self._refresh_active_job_label()
            return existing

        # Convenience boundary: only a completely empty job list may create
        # the first job from Source. If any job exists, do not invent JOB-xxx.
        if len(self.jobs) != 0:
            return None

        job = self.jobs.new_job(None)
        set_owner = getattr(job, "set_owner_identity", None)
        current_identity = getattr(self, "current_user_identity", None)
        if callable(set_owner) and callable(current_identity):
            set_owner(current_identity())

        job.profile_id = self.active_profile_id
        job.source_extraction = path
        self.current_job = job

        self.workflow.clear()
        self.workflow_panel.refresh()
        self._refresh_active_job_label()
        self._update_run_button()

        self.status_bar.set_status(
            f"{job.job_id} opprettet automatisk fra første Source"
        )

        jobs_window = getattr(self, "jobs_window", None)
        if jobs_window is not None:
            try:
                if jobs_window.winfo_exists():
                    jobs_window.refresh()
            except Exception:
                pass

        return job


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
