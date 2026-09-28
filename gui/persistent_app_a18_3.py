from __future__ import annotations

import json

from . import theme
from .depot_result_center_a18_3 import DepotResultCenterDialogA18_3
from .persistent_app_a18_2 import WorkflowApp as A18_2WorkflowApp
from .window_placement import present_child_over_parent, release_parent_work_window


class WorkflowApp(A18_2WorkflowApp):
    """v0.1.6-a18.3: visible inline period-review controls."""

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
            return super(A18_2WorkflowApp, self)._open_depot_assessment()
        try:
            model = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            return super(A18_2WorkflowApp, self)._open_depot_assessment()

        dialog = DepotResultCenterDialogA18_3(
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
