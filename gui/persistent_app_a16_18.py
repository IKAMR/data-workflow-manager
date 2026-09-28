from __future__ import annotations

from . import theme
from .persistent_app_a16_17 import WorkflowApp as A16_17WorkflowApp
from .depot_result_center_a16_18 import DepotResultCenterDialogA16_18


class WorkflowApp(A16_17WorkflowApp):
    """v0.1.6-a16.18: compact archive-part summary surface."""

    def _open_depot_assessment(self) -> None:
        model, report_path = self._load_depot_result_model()
        if model is None:
            return
        dialog = DepotResultCenterDialogA16_18(
            self,
            model=model,
            report_path=report_path,
            user_identity=self.current_user_identity(),
        )
        dialog.focus()


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
