from __future__ import annotations

from tkinter import messagebox

from version import APP_NAME
from .depot_assessment_dialog_a23 import DepotAssessmentDialogA23
from .depot_result_views_a24 import DepotResultViewsDialogA24
from .window_placement import enable_native_work_window, present_native_work_window


class DepotAssessmentDialogA24(DepotAssessmentDialogA23):
    """v0.1.6-a4: generic assessment with safe native work-window chrome."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        enable_native_work_window(self)
        present_native_work_window(self)

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

        dialog = DepotResultViewsDialogA24(
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
