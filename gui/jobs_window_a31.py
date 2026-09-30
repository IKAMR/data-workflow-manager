from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from noark5_workflow.core.job import Job
from . import theme
from .job_batch_action_dialog import JobBatchActionDialog
from .jobs_window_a30 import A30JobsWindow


class A31JobsWindow(A30JobsWindow):
    """a24.6: multi-job selection and reusable batch actions."""

    def __init__(
        self,
        *args,
        on_fill_storage_suggestions: Callable[[tuple[Job, ...]], None] | None = None,
        **kwargs,
    ) -> None:
        self.on_fill_storage_suggestions = (
            on_fill_storage_suggestions or (lambda _jobs: None)
        )
        self._job_actions_dialog = None
        super().__init__(*args, **kwargs)
        self._install_job_actions_button()

    def _install_job_actions_button(self) -> None:
        parent = self.new_button.master
        self.job_actions_button = ctk.CTkButton(
            parent,
            text="Jobbhandlinger...",
            command=self._open_job_actions,
            width=132,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self.job_actions_button.pack(
            side="left",
            padx=(0, 8),
            before=self.start_all_button,
        )

    def _open_job_actions(self) -> None:
        if self._batch_running:
            return
        existing = self._job_actions_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.focus()
                    existing.lift()
                    return
            except Exception:
                self._job_actions_dialog = None

        dialog = JobBatchActionDialog(
            self,
            self.batch.jobs(),
            on_fill_storage_suggestions=self._run_fill_storage_suggestions,
        )
        self._job_actions_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._job_actions_closed(event, d),
            add="+",
        )

    def _job_actions_closed(self, event, dialog) -> None:
        if getattr(event, "widget", None) is not dialog:
            return
        if self._job_actions_dialog is dialog:
            self._job_actions_dialog = None

    def _run_fill_storage_suggestions(self, jobs: tuple[Job, ...]) -> None:
        self.on_fill_storage_suggestions(jobs)
        self.refresh()

    def set_batch_running(self, running: bool) -> None:
        super().set_batch_running(running)
        if hasattr(self, "job_actions_button"):
            self.job_actions_button.configure(
                state="disabled" if running else "normal"
            )
