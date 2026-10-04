from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from app.workflow_sequences import noark5_workflow_labels
from noark5_workflow.core.job import Job
from . import theme
from .jobs_window_a34 import A34JobsWindow


class A35JobsWindow(A34JobsWindow):
    """a37: explicit Noark 5 workflow choice for selected jobs.

    Keeps Jobbliste alive when a job is opened so the window can be shown again
    without rebuilding the complete Jobbliste widget tree.
    """

    def __init__(
        self,
        *args,
        on_apply_workflow: Callable[[tuple[Job, ...], str], None] | None = None,
        **kwargs,
    ) -> None:
        self.on_apply_workflow = on_apply_workflow or (
            lambda _jobs, _sequence_id: None
        )
        super().__init__(*args, **kwargs)

    def _install_bulk_workflow_actions(self) -> None:
        parent = self.start_all_button.master
        labels = noark5_workflow_labels(settings=self.settings)
        labels = {key: value for key, value in labels.items() if key != "none"}
        self._workflow_labels = labels
        self._workflow_ids_by_label = {value: key for key, value in labels.items()}

        configured = str(
            self.settings.get("noark5_discovery_workflow", "noark5_standard")
            or "noark5_standard"
        )
        if configured not in labels:
            configured = (
                "noark5_standard"
                if "noark5_standard" in labels
                else next(iter(labels), "")
            )

        default_label = labels.get(
            configured,
            next(iter(labels.values()), "Noark 5 – standard"),
        )
        self._workflow_choice = ctk.StringVar(value=default_label)
        self.workflow_menu = ctk.CTkOptionMenu(
            parent,
            variable=self._workflow_choice,
            values=list(labels.values()) or ["Noark 5 – standard"],
            width=235,
            fg_color=theme.BUTTON_BG,
            button_color=theme.BLUE_DIM,
            button_hover_color=theme.BLUE,
        )
        self.workflow_menu.pack(
            side="left", padx=(0, 6), before=self.start_all_button
        )

        self.standard_selected_button = ctk.CTkButton(
            parent,
            text="Bruk på valgte",
            command=self._apply_workflow_selected,
            width=115,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self.standard_selected_button.pack(
            side="left", padx=(0, 6), before=self.start_all_button
        )

        self.standard_empty_button = ctk.CTkButton(
            parent,
            text="Standard tomme",
            command=self._apply_standard_empty,
            width=122,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self.standard_empty_button.pack(
            side="left", padx=(0, 6), before=self.start_all_button
        )

    def _apply_workflow_selected(self) -> None:
        selected = self._selected_for_action()
        if not selected:
            return
        sequence_id = self._workflow_ids_by_label.get(
            self._workflow_choice.get(), ""
        )
        if sequence_id:
            self.on_apply_workflow(selected, sequence_id)

    def _open(self, job: Job) -> None:
        """Open the job and hide, rather than destroy, Jobbliste.

        Pressing JOBBER afterwards reuses this exact same window instance.
        This avoids the unstable destroy/recreate cycle observed on Windows.
        """
        self.on_open_job(job)
        try:
            self.refresh()
            self.withdraw()
        except Exception:
            pass

    def _update_bulk_action_state(self) -> None:
        if not hasattr(self, "standard_selected_button"):
            return
        selected = bool(self._selected_job_ids_for_run())
        state = "disabled" if self._batch_running else "normal"
        if hasattr(self, "workflow_menu"):
            self.workflow_menu.configure(state=state)
        self.standard_selected_button.configure(
            state="disabled" if self._batch_running or not selected else "normal"
        )
        self.standard_empty_button.configure(
            state="disabled"
            if self._batch_running or len(self.batch) == 0
            else "normal"
        )
