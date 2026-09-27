from __future__ import annotations

import json

from . import theme
from .depot_result_center_a14_4 import DepotResultCenterDialogA14_4
from .persistent_app_a14_3 import WorkflowApp as A14_3WorkflowApp
from .window_placement import present_child_over_parent, release_parent_work_window


class WorkflowApp(A14_3WorkflowApp):
    """v0.1.6-a14.4: clearer result hierarchy and tabular file statistics."""

    def _open_depot_assessment(self) -> None:
        self._hide_workflow_tooltips()
        existing = getattr(self, "_depot_assessment_dialog", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    release_parent_work_window(self)
                    existing.deiconify()
                    present_child_over_parent(existing, self)
                    return
            except Exception:
                self._depot_assessment_dialog = None

        report_path, _work_operations, _unavailable_path = self._depot_report_for_job(self.current_job)
        if report_path is None:
            return super()._open_depot_assessment()
        try:
            model = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            return super()._open_depot_assessment()

        dialog = DepotResultCenterDialogA14_4(
            self, model=model, report_path=report_path,
            user_identity=self.current_user_identity(),
        )
        self._depot_assessment_dialog = dialog
        dialog.bind("<Destroy>", lambda event, d=dialog: self._depot_assessment_closed(event, d), add="+")


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
