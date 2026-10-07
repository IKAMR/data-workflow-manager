from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from noark5_workflow.core.job import Job
from . import theme
from .job_batch_action_dialog import JobBatchActionDialog


class V017A1JobBatchActionDialog(JobBatchActionDialog):
    """v0.1.7-a1: metadata actions for selected jobs."""

    def __init__(
        self,
        *args,
        on_edit_metadata: Callable[[tuple[Job, ...]], None] | None = None,
        **kwargs,
    ) -> None:
        self._on_edit_metadata = on_edit_metadata
        super().__init__(*args, **kwargs)
        toolbar = self._fill_button.master
        self._metadata_button = ctk.CTkButton(
            toolbar,
            text="Metadata…",
            width=145,
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
            command=self._run_edit_metadata,
        )
        self._metadata_button.grid(row=1, column=4, columnspan=3, padx=(18, 0), pady=(8, 0), sticky="e")
        self._update_count()

    def _update_count(self) -> None:
        super()._update_count()
        if not hasattr(self, "_metadata_button"):
            return
        selected = bool(self._selected())
        self._metadata_button.configure(
            state="normal" if selected and self._on_edit_metadata is not None else "disabled"
        )

    def _run_edit_metadata(self) -> None:
        selected = self._selected()
        if selected and self._on_edit_metadata is not None:
            self._on_edit_metadata(selected)
