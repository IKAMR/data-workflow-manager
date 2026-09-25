from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from version import APP_NAME
from .depot_assessment_dialog_a30 import DepotAssessmentDialogA30
from .depot_result_views_a31 import DepotResultViewsDialogA31


class DepotAssessmentDialogA31(DepotAssessmentDialogA30):
    """v0.1.6-a11: route depot assessment to the operational dashboard."""

    def __init__(
        self,
        master,
        *,
        user_identity=None,
        work_operations=None,
        storage_unavailable_path: str | Path | None = None,
    ):
        super().__init__(
            master,
            user_identity=user_identity,
            work_operations=work_operations,
            storage_unavailable_path=storage_unavailable_path,
        )

    def _open_result_views(self) -> None:
        if self.report_model is None:
            messagebox.showinfo(
                APP_NAME,
                "Velg eller last en depotvalideringsrapport først.",
                parent=self,
            )
            return

        existing = self._result_views_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.focus()
                    existing.lift()
                    return
            except Exception:
                pass

        dialog = DepotResultViewsDialogA31(
            self,
            model=self.report_model,
            report_path=self.report_path,
            user_identity=self.user.as_dict() if self.user else None,
        )
        self._result_views_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._result_views_closed(event, d),
            add="+",
        )
