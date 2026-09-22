from __future__ import annotations

from pathlib import Path

from . import theme
from .direct_depot_assessment_dialog_a11 import DirectDepotAssessmentDialogA11
from .noark5_control_overview_dialog_a11 import Noark5ControlOverviewDialogA11
from .persistent_app_a42 import WorkflowApp as A42WorkflowApp


class WorkflowApp(A42WorkflowApp):
    """v0.1.4-a11: direct control-overview -> depot-assessment workflow."""

    def _open_validation_overview(self) -> None:
        html_path = self._latest_validation_overview_path()
        json_path = self._latest_validation_overview_json_path()
        if html_path is None or json_path is None:
            self.status_bar.set_status("Ingen komplett Noark 5 kontrolloversikt er generert ennå")
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

        identity = self.current_user_identity()

        dialog = Noark5ControlOverviewDialogA11(
            parent,
            overview_json=json_path,
            overview_html=html_path,
            user_identity=identity,
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

        self.status_bar.set_status(f"Åpnet kontrolloversikt: {html_path.name}")


    def _open_depot_assessment(self) -> None:
        """Open depot assessment for the active job's effective Work area.

        Job.work_operations is the configured/base Work root. Results from the
        current job may live below the effective app/subfolder path, e.g.
        repository_operations\\dwm\\a03. Use that effective path when available.
        """
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

        report_path = None
        if work_operations:
            from .depot_assessment_dialog import latest_depot_report
            report_path = latest_depot_report(work_operations)

        if report_path is None:
            from .depot_assessment_dialog import DepotAssessmentDialog
            dialog = DepotAssessmentDialog(
                self,
                user_identity=self.current_user_identity(),
                work_operations=work_operations,
            )
        else:
            dialog = DirectDepotAssessmentDialogA11(
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
            dialog.after_idle(dialog.lift)
        except Exception:
            pass


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
