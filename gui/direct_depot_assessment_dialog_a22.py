from __future__ import annotations

from tkinter import messagebox

from version import APP_NAME
from .depot_result_views_a22 import DepotResultViewsDialogA22
from .direct_depot_assessment_dialog_a21 import DirectDepotAssessmentDialogA21


class DirectDepotAssessmentDialogA22(DirectDepotAssessmentDialogA21):
    """v0.1.6-a2: route direct assessment to archive-part-first result views."""

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

        dialog = DepotResultViewsDialogA22(
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
        try:
            dialog.update_idletasks()
            dialog.lift()
            dialog.focus_force()
        except Exception:
            pass
