from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from version import APP_NAME
from . import theme
from .jobs_window_a21 import A21JobsWindow


class A22JobsWindow(A21JobsWindow):
    """a5 fix: reset execution state directly for jobs already in the list."""

    def __init__(self, *args, reset_job_execution=None, **kwargs) -> None:
        self.reset_job_execution = (
            reset_job_execution
            or (lambda _job: (False, "Nullstilling er ikke tilgjengelig."))
        )
        super().__init__(*args, **kwargs)

    def _row(
        self,
        row,
        job,
        *,
        active=False,
        can_move_up=True,
        can_move_down=True,
    ) -> None:
        super()._row(
            row,
            job,
            active=active,
            can_move_up=can_move_up,
            can_move_down=can_move_down,
        )
        view = self._row_views.get(job.job_id)
        if view is None:
            return

        top = view["open"].master
        reset_button = ctk.CTkButton(
            top,
            text="Nullstill",
            width=72,
            height=27,
            command=lambda j=job: self._reset_job(j),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        reset_button.grid(row=0, column=11, padx=(4, 0))
        view["reset"] = reset_button
        reset_button.configure(
            state="disabled" if self._batch_running else "normal"
        )

    def _update_row_view(
        self,
        row,
        job,
        *,
        active,
        can_move_up,
        can_move_down,
    ) -> None:
        super()._update_row_view(
            row,
            job,
            active=active,
            can_move_up=can_move_up,
            can_move_down=can_move_down,
        )
        view = self._row_views.get(job.job_id)
        if view is not None and "reset" in view:
            view["reset"].configure(
                state="disabled" if self._batch_running else "normal"
            )

    def _reset_job(self, job) -> None:
        if self._batch_running:
            return
        if not messagebox.askyesno(
            APP_NAME,
            f"Nullstille kjørestatus/cursor for {job.job_id}?\n\n"
            "Jobben settes klar for ny kjøring fra start.\n"
            "Resultatfiler og logger på disk slettes ikke.",
        ):
            return

        ok, message = self.reset_job_execution(job)
        if not ok:
            messagebox.showerror(APP_NAME, message)
            return
        self.refresh()
