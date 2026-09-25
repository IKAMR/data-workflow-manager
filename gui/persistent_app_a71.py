from __future__ import annotations

from . import theme
from .depot_assessment_dialog_a31 import DepotAssessmentDialogA31
from .direct_depot_assessment_dialog_a31 import DirectDepotAssessmentDialogA31
from .noark5_control_overview_dialog_a31 import Noark5ControlOverviewDialogA31
from .persistent_app_a70 import WorkflowApp as A70WorkflowApp


class WorkflowApp(A70WorkflowApp):
    """v0.1.6-a11: activate the operational depot dashboard."""

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

        dialog = Noark5ControlOverviewDialogA31(
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
        report_path, work_operations, unavailable_path = (
            self._depot_report_for_job(job)
        )

        if report_path is None:
            dialog = DepotAssessmentDialogA31(
                self,
                user_identity=self.current_user_identity(),
                work_operations=work_operations,
                storage_unavailable_path=unavailable_path,
            )
        else:
            dialog = DirectDepotAssessmentDialogA31(
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


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
