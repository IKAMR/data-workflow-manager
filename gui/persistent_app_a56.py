from __future__ import annotations

import customtkinter as ctk

from . import theme
from .persistent_app_a55 import WorkflowApp as A55WorkflowApp


class WorkflowApp(A55WorkflowApp):
    """v0.1.5-a21: create a new empty job list directly from the main window."""

    def __init__(self) -> None:
        super().__init__()
        self._install_new_job_list_control()
        self._refresh_main_job_list_controls()

    def _install_new_job_list_control(self) -> None:
        panel = self.workflow_panel
        parent = panel.open_project_button.master

        # Keep the meaning explicit: this creates a new job list. Adding a
        # second job to the current list remains a Jobber-dialog operation.
        self.new_job_list_button = ctk.CTkButton(
            parent,
            text="Ny jobbliste",
            command=self._new_job_list,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            height=28,
            font=theme.font(theme.SMALL_SIZE),
        )
        self.new_job_list_button.grid(
            row=2,
            column=0,
            columnspan=2,
            padx=0,
            pady=(6, 0),
            sticky="ew",
        )

    def _refresh_main_job_list_controls(self) -> None:
        super()._refresh_main_job_list_controls()
        if hasattr(self, "new_job_list_button"):
            state = "disabled" if self.batch_running else "normal"
            self.new_job_list_button.configure(state=state)


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
