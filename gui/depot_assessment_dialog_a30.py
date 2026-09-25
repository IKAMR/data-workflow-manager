from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from version import APP_NAME
from .depot_assessment_dialog_a29 import DepotAssessmentDialogA29
from .depot_result_views_a30 import DepotResultViewsDialogA30


class DepotAssessmentDialogA30(DepotAssessmentDialogA29):
    """v0.1.6-a10: target-GUI archive surface + explicit storage state."""

    def __init__(
        self,
        master,
        *,
        user_identity=None,
        work_operations=None,
        storage_unavailable_path: str | Path | None = None,
    ):
        self.storage_unavailable_path = (
            Path(storage_unavailable_path)
            if storage_unavailable_path
            else None
        )

        super().__init__(
            master,
            user_identity=user_identity,
            work_operations=work_operations,
        )

        if self.storage_unavailable_path is not None and self.report_model is None:
            expected = str(self.storage_unavailable_path)
            self.report_var.set("Lagringsområdet for aktiv jobb er ikke tilgjengelig")
            self.current_var.set(
                "Depotvurdering kan ikke lastes før lagringsområdet er tilgjengelig."
            )
            self._set_report_text(
                "LAGRING UTILGJENGELIG\n\n"
                "Lagringsområdet for aktiv jobb er ikke tilgjengelig.\n"
                "Koble til / lås opp lagringen og prøv igjen.\n\n"
                f"Forventet Work-bane:\n{expected}\n\n"
                "Dette betyr ikke at depotvalideringsrapporten mangler."
            )
            self.result_views_button.configure(state="disabled")
            self.open_report_button.configure(state="disabled")

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

        dialog = DepotResultViewsDialogA30(
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
