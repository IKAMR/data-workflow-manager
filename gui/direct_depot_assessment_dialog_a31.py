from __future__ import annotations

from tkinter import messagebox

from version import APP_NAME
from .depot_result_views_a31 import DepotResultViewsDialogA31
from .direct_depot_assessment_dialog_a30 import DirectDepotAssessmentDialogA30


class DirectDepotAssessmentDialogA31(DirectDepotAssessmentDialogA30):
    """v0.1.6-a11: route direct assessment to the operational dashboard."""

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
