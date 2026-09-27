from __future__ import annotations

from . import theme
from .depot_result_center_a14_2 import DepotResultCenterDialogA14_2
from .persistent_app_a14_1 import WorkflowApp as A14_1WorkflowApp


class WorkflowApp(A14_1WorkflowApp):
    """v0.1.6-a14.2: use the simplified six-area result center."""

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

        report_path, _work_operations, _unavailable_path = self._depot_report_for_job(self.current_job)
        if report_path is None:
            return super()._open_depot_assessment()

        try:
            import json
            model = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            return super()._open_depot_assessment()

        dialog = DepotResultCenterDialogA14_2(
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
