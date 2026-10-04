from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from noark5_workflow.core.job import Job
from . import theme
from .jobs_window_a33 import A33JobsWindow


class A34JobsWindow(A33JobsWindow):
    """a36: visible multi-job selection and bulk default-workflow actions."""

    def __init__(
        self,
        *args,
        on_apply_standard: Callable[[tuple[Job, ...], bool], None] | None = None,
        **kwargs,
    ) -> None:
        self.on_apply_standard = on_apply_standard or (lambda _jobs, _empty_only: None)
        self._selection_vars: dict[str, ctk.BooleanVar] = {}
        super().__init__(*args, **kwargs)
        self._install_bulk_workflow_actions()

    def _install_bulk_workflow_actions(self) -> None:
        parent = self.start_all_button.master
        self.standard_selected_button = ctk.CTkButton(
            parent, text="Standard valgte", command=self._apply_standard_selected,
            width=122, fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        self.standard_selected_button.pack(side="left", padx=(0, 6), before=self.start_all_button)
        self.standard_empty_button = ctk.CTkButton(
            parent, text="Standard tomme", command=self._apply_standard_empty,
            width=122, fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        self.standard_empty_button.pack(side="left", padx=(0, 6), before=self.start_all_button)

    def _invalidate_selection_render(self) -> None:
        self._rendered_job_ids = ()
        self._row_views.clear()
        self._selection_vars.clear()

    def _select_all(self) -> None:
        self._selected_job_ids = {job.job_id for job in self.batch.jobs()}
        self._invalidate_selection_render()
        self.refresh()

    def _clear_selection(self) -> None:
        self._selected_job_ids = set()
        self._invalidate_selection_render()
        self.refresh()

    def _toggle_selection(self, job_id: str) -> None:
        if job_id in self._selected_job_ids:
            self._selected_job_ids.remove(job_id)
        else:
            self._selected_job_ids.add(job_id)
        self._invalidate_selection_render()
        self.refresh()

    def _row(self, row, job, *, active=False, can_move_up=True, can_move_down=True) -> None:
        super()._row(row, job, active=active, can_move_up=can_move_up, can_move_down=can_move_down)
        view = self._row_views.get(job.job_id)
        if view is None:
            return

        top = view["id"].master
        for key in ("id", "name", "status", "progress", "worker", "up", "down",
                    "open", "mapper", "standard", "reset", "delete"):
            widget = view.get(key)
            if widget is None:
                continue
            info = widget.grid_info()
            widget.grid_configure(column=int(info.get("column", 0)) + 1)

        selected = job.job_id in self._selected_job_ids_for_run()
        var = ctk.BooleanVar(value=selected)
        self._selection_vars[job.job_id] = var
        checkbox = ctk.CTkCheckBox(
            top, text="", width=26, variable=var,
            command=lambda jid=job.job_id: self._toggle_selection(jid),
        )
        checkbox.grid(row=0, column=0, padx=(0, 6), sticky="w")
        view["select"] = checkbox

    def _update_row_view(self, row, job, *, active, can_move_up, can_move_down) -> None:
        super()._update_row_view(
            row, job, active=active, can_move_up=can_move_up, can_move_down=can_move_down
        )
        var = self._selection_vars.get(job.job_id)
        if var is not None:
            var.set(job.job_id in self._selected_job_ids_for_run())
        view = self._row_views.get(job.job_id)
        if view is not None and "select" in view:
            view["select"].configure(state="disabled" if self._batch_running else "normal")

    def refresh(self) -> None:
        super().refresh()
        # Base selection toolbar owns row 0; job cards start at row 1.
        for index, job in enumerate(self.batch.jobs(), start=1):
            view = self._row_views.get(job.job_id)
            if view is not None:
                view["card"].grid_configure(row=index)
        self._update_bulk_action_state()

    def _selected_for_action(self) -> tuple[Job, ...]:
        return self._selected_jobs_for_run()

    def _apply_standard_selected(self) -> None:
        selected = self._selected_for_action()
        if selected:
            self.on_apply_standard(selected, False)

    def _apply_standard_empty(self) -> None:
        self.on_apply_standard(tuple(self.batch.jobs()), True)

    def _update_bulk_action_state(self) -> None:
        if not hasattr(self, "standard_selected_button"):
            return
        selected = bool(self._selected_job_ids_for_run())
        self.standard_selected_button.configure(
            state="disabled" if self._batch_running or not selected else "normal"
        )
        self.standard_empty_button.configure(
            state="disabled" if self._batch_running or len(self.batch) == 0 else "normal"
        )

    def set_batch_running(self, running: bool) -> None:
        super().set_batch_running(running)
        self._update_bulk_action_state()
