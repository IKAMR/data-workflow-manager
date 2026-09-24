from __future__ import annotations

from . import theme
from .depot_assessment_dialog import latest_depot_report
from .depot_assessment_dialog_a23 import DepotAssessmentDialogA23
from .direct_depot_assessment_dialog_a23 import DirectDepotAssessmentDialogA23
from .noark5_control_overview_dialog_a23 import Noark5ControlOverviewDialogA23
from .persistent_app_a62 import WorkflowApp as A62WorkflowApp


class WorkflowApp(A62WorkflowApp):
    """v0.1.6-a3: activate searchable archive-part Noark 5 result review."""

    def _open_validation_overview(self) -> None:
        html_path = self._latest_validation_overview_path()
        json_path = self._latest_validation_overview_json_path()
        if html_path is None or json_path is None:
            self.status_bar.set_status(
                "Ingen komplett Noark 5 kontrolloversikt er generert ennå"
            )
            return

        existing = self._control_overview_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.destroy()
            except Exception:
                pass

        parent = self
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    parent = self.jobs_window
            except Exception:
                pass

        dialog = Noark5ControlOverviewDialogA23(
            parent,
            overview_json=json_path,
            overview_html=html_path,
            user_identity=self.current_user_identity(),
        )
        self._control_overview_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._control_overview_closed(event, d),
            add="+",
        )
        try:
            dialog.update_idletasks()
            dialog.lift()
            dialog.focus_force()
            dialog.after_idle(dialog.lift)
        except Exception:
            pass

    def _open_depot_assessment(self) -> None:
        self._hide_workflow_tooltips()

        existing = self._depot_assessment_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.focus()
                    existing.lift()
                    return
            except Exception:
                pass

        job = self.current_job
        work_operations = None
        if job is not None:
            work_operations = (
                getattr(job, "_effective_work_operations", None)
                or getattr(job, "work_operations", None)
            )

        report_path = latest_depot_report(work_operations) if work_operations else None

        if report_path is None:
            dialog = DepotAssessmentDialogA23(
                self,
                user_identity=self.current_user_identity(),
                work_operations=work_operations,
            )
        else:
            dialog = DirectDepotAssessmentDialogA23(
                self,
                report_path=report_path,
                user_identity=self.current_user_identity(),
            )

        self._depot_assessment_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._depot_assessment_closed(event, d),
            add="+",
        )
        try:
            dialog.update_idletasks()
            dialog.lift()
            dialog.focus_force()
        except Exception:
            pass


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
