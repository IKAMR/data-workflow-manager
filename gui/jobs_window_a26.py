from __future__ import annotations

import customtkinter as ctk

from . import theme
from .jobs_window_a25 import A25JobsWindow


class A26JobsWindow(A25JobsWindow):
    """a8: quick access to the latest Noark 5 batch control overview."""

    def __init__(
        self,
        *args,
        open_validation_overview=None,
        has_validation_overview=None,
        **kwargs,
    ) -> None:
        self.open_validation_overview = open_validation_overview or (lambda: None)
        self.has_validation_overview = has_validation_overview or (lambda: False)
        super().__init__(*args, **kwargs)
        self._install_validation_overview_action()
        self._update_validation_overview_state()

    def _install_validation_overview_action(self) -> None:
        parent = self.start_all_button.master
        self.validation_overview_button = ctk.CTkButton(
            parent,
            text="Kontrolloversikt",
            command=self.open_validation_overview,
            width=125,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self.validation_overview_button.pack(
            side="left",
            padx=(10, 6),
            before=self.stop_button,
        )

    def _update_validation_overview_state(self) -> None:
        if not hasattr(self, "validation_overview_button"):
            return
        enabled = bool(self.has_validation_overview()) and not self._batch_running
        self.validation_overview_button.configure(
            state="normal" if enabled else "disabled"
        )

    def refresh(self) -> None:
        super().refresh()
        self._update_validation_overview_state()

    def set_batch_running(self, running: bool) -> None:
        super().set_batch_running(running)
        self._update_validation_overview_state()
