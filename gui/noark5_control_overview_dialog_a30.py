from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from version import APP_NAME
from .direct_depot_assessment_dialog_a30 import DirectDepotAssessmentDialogA30
from .noark5_control_overview_dialog_a29 import Noark5ControlOverviewDialogA29


class Noark5ControlOverviewDialogA30(Noark5ControlOverviewDialogA29):
    """v0.1.6-a10: route overview to target-GUI archive surface."""

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

        dialog = DirectDepotAssessmentDialogA30(
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
