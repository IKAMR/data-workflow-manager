from __future__ import annotations

from . import theme
from .depot_result_center_a14_1 import DepotResultCenterDialogA14_1
from .persistent_app_a13_runtime import WorkflowApp as A13RuntimeWorkflowApp


class WorkflowApp(A13RuntimeWorkflowApp):
    """v0.1.6-a14.1: simplify the result/depot dialog hierarchy."""

    def _open_depot_assessment(self) -> None:
        self._hide_workflow_tooltips()

        existing = getattr(self, "_depot_assessment_dialog", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    try:
                        existing.focus_force()
                    except Exception:
                        existing.focus()
                    return
            except Exception:
                self._depot_assessment_dialog = None

        job = self.current_job
        report_path, work_operations, unavailable_path = self._depot_report_for_job(job)

        # The a14.1 simplification is deliberately conservative: when a report
        # exists, open one Resultatvisninger window directly.  When no report
        # exists, retain the established a13 flow for report discovery and
        # storage-unavailable diagnostics.
        if report_path is None:
            return super()._open_depot_assessment()

        try:
            import json

            model = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            # Preserve the proven fallback path if the report cannot be read.
            return super()._open_depot_assessment()

        dialog = DepotResultCenterDialogA14_1(
            self,
            model=model,
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
