from __future__ import annotations
from . import theme
from .direct_depot_assessment_dialog_a17 import DirectDepotAssessmentDialogA17
from .noark5_control_overview_dialog_a17 import Noark5ControlOverviewDialogA17
from .persistent_app_a48 import WorkflowApp as A48WorkflowApp

class WorkflowApp(A48WorkflowApp):
    """v0.1.5-a7: filtered combined coverage with Arkade evidence drill-down."""

    def _open_validation_overview(self) -> None:
        html_path = self._latest_validation_overview_path(); json_path = self._latest_validation_overview_json_path()
        if html_path is None or json_path is None:
            self.status_bar.set_status("Ingen komplett Noark 5 kontrolloversikt er generert ennå"); return
        existing = self._control_overview_dialog
        if existing is not None:
            try:
                if existing.winfo_exists(): existing.destroy()
            except Exception: pass
        parent = self
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists(): parent = self.jobs_window
            except Exception: pass
        dialog = Noark5ControlOverviewDialogA17(parent, overview_json=json_path, overview_html=html_path, user_identity=self.current_user_identity())
        self._control_overview_dialog = dialog
        dialog.bind("<Destroy>", lambda event, d=dialog: self._control_overview_closed(event, d), add="+")
        try:
            dialog.update_idletasks(); dialog.lift(); dialog.focus_force(); dialog.after_idle(dialog.lift)
        except Exception: pass

    def _open_depot_assessment(self) -> None:
        self._hide_workflow_tooltips()
        existing = self._depot_assessment_dialog
        if existing is not None:
            try:
                if existing.winfo_exists(): existing.focus(); existing.lift(); return
            except Exception: pass
        job = self.current_job
        work_operations = None
        if job is not None:
            work_operations = getattr(job, "_effective_work_operations", None) or getattr(job, "work_operations", None)
        report_path = None
        if work_operations:
            from .depot_assessment_dialog import latest_depot_report
            report_path = latest_depot_report(work_operations)
        if report_path is None:
            from .depot_assessment_dialog import DepotAssessmentDialog
            dialog = DepotAssessmentDialog(self, user_identity=self.current_user_identity(), work_operations=work_operations)
        else:
            dialog = DirectDepotAssessmentDialogA17(self, report_path=report_path, user_identity=self.current_user_identity())
        self._depot_assessment_dialog = dialog
        dialog.bind("<Destroy>", lambda event, d=dialog: self._depot_assessment_closed(event, d), add="+")
        try:
            dialog.update_idletasks(); dialog.lift(); dialog.focus_force()
        except Exception: pass

def run_gui() -> None:
    theme.apply_theme(); app = WorkflowApp(); app.mainloop()
