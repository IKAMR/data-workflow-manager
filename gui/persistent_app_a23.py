from __future__ import annotations

from .persistent_app_a17 import WorkflowApp as A17WorkflowApp
from .persistent_app_a22 import WorkflowApp as A22WorkflowApp


class WorkflowApp(A22WorkflowApp):
    """a15.4 fixes the clean-job-list boundary.

    Earlier runtime layers both participated in new-list creation, which could
    leave two blank draft jobs. Bypass the duplicate-producing override and use
    the established a17 clear/reset boundary, then create exactly one draft.
    """

    def _new_job_list(self) -> bool:
        if not A17WorkflowApp._new_job_list(self):
            return False

        # New lists start in the generic/default profile and contain one blank
        # draft only. _create_job owns user identity and the one Mapper dialog.
        self._apply_profile(None, persist=False)
        job = self._create_job(None)
        job.profile_id = None

        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.refresh()
        self.status_bar.set_status(
            "Ny jobbliste - konfigurer Source, Work og Storage"
        )
        return True


def run_gui() -> None:
    from . import theme
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
