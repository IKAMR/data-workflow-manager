from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from version import APP_NAME
from .direct_depot_assessment_dialog_a24 import DirectDepotAssessmentDialogA24
from .noark5_control_overview_dialog_a23 import Noark5ControlOverviewDialogA23
from .window_placement import enable_native_work_window, present_native_work_window


class Noark5ControlOverviewDialogA24(Noark5ControlOverviewDialogA23):
    """v0.1.6-a4: overview with safe native work-window chrome."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        enable_native_work_window(self)
        present_native_work_window(self)

    def _open_assessment(self, report_path: Path | None) -> None:
        if report_path is None or not report_path.is_file():
            messagebox.showwarning(
                APP_NAME,
                "Depotrapporten finnes ikke lenger på forventet sted.",
                parent=self,
            )
            return

        existing = self._assessment_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.destroy()
            except Exception:
                pass

        dialog = DirectDepotAssessmentDialogA24(
            self,
            report_path=report_path,
            user_identity=self.user_identity,
        )
        self._assessment_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._assessment_closed(event, d),
            add="+",
        )
