from __future__ import annotations

import json

import customtkinter as ctk

from . import theme
from .depot_result_center_a14_3 import DepotResultCenterDialogA14_3
from .persistent_app_a14_2 import WorkflowApp as A14_2WorkflowApp
from .window_placement import present_child_over_parent, release_parent_work_window


class WorkflowApp(A14_2WorkflowApp):
    """v0.1.6-a14.3: clarify result actions and stabilize result-window opening."""

    def __init__(self) -> None:
        super().__init__()
        self._arrange_result_log_actions()
        self.after_idle(self._arrange_result_log_actions)

    def _arrange_result_log_actions(self) -> None:
        """Keep interpreted depot results before technical raw-result history.

        The long-standing Resultater action is the append-only raw-result bank,
        not the consolidated result/depot view.  Rename it Råresultater and place
        it immediately after Depotvurdering so the visible order becomes:

            Depotvurdering | Råresultater | Vis siste | Tøm
        """
        log_panel = getattr(self, "log_panel", None)
        header = getattr(log_panel, "header", None)
        if header is None:
            return

        buttons = {}
        for child in header.winfo_children():
            if not isinstance(child, ctk.CTkButton):
                continue
            try:
                text = str(child.cget("text"))
            except Exception:
                continue
            buttons[text] = child

        raw = buttons.get("Resultater") or buttons.get("Råresultater")
        if raw is not None:
            try:
                raw.configure(text="Råresultater", width=92)
            except Exception:
                pass

        desired = (
            ("Depotvurdering", 1),
            ("Råresultater", 2),
            ("Vis siste", 3),
            ("Vis alle", 3),
            ("Tøm", 4),
        )
        # Re-read labels after the rename above.
        current = {}
        for child in header.winfo_children():
            if not isinstance(child, ctk.CTkButton):
                continue
            try:
                current[str(child.cget("text"))] = child
            except Exception:
                pass

        for label, column in desired:
            button = current.get(label)
            if button is None:
                continue
            try:
                info = button.grid_info()
                if info:
                    button.grid_configure(column=column)
            except Exception:
                pass

        try:
            header.grid_columnconfigure(0, weight=1)
            for column in range(1, 5):
                header.grid_columnconfigure(column, weight=0)
        except Exception:
            pass

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

        report_path, _work_operations, _unavailable_path = self._depot_report_for_job(
            self.current_job
        )
        if report_path is None:
            return super()._open_depot_assessment()

        try:
            model = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            return super()._open_depot_assessment()

        dialog = DepotResultCenterDialogA14_3(
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
