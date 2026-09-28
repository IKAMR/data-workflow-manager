from __future__ import annotations

import customtkinter as ctk

from . import theme
from .persistent_app_a19_2 import WorkflowApp as A19_2WorkflowApp


class WorkflowApp(A19_2WorkflowApp):
    """v0.1.6-a19.3: explicit main-window loading overlay while results open."""

    def _a193_depot_buttons(self):
        found = []
        stack = [self]
        while stack:
            parent = stack.pop()
            try:
                children = list(parent.winfo_children())
            except Exception:
                continue
            stack.extend(children)
            for widget in children:
                try:
                    if isinstance(widget, ctk.CTkButton) and str(widget.cget("text") or "").strip() == "Depotvurdering":
                        found.append(widget)
                except Exception:
                    pass
        return found

    def _a192_begin_open_indicator(self) -> None:
        # Keep the a19.2 status-bar feedback as a secondary signal.
        super()._a192_begin_open_indicator()

        self._a193_disabled_depot_buttons = []
        for button in self._a193_depot_buttons():
            try:
                previous_state = str(button.cget("state") or "normal")
                self._a193_disabled_depot_buttons.append((button, previous_state))
                button.configure(state="disabled")
            except Exception:
                pass

        old = getattr(self, "_a193_open_overlay", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass

        panel = ctk.CTkFrame(
            self,
            fg_color=theme.PANEL_BG,
            border_width=1,
            border_color=theme.BLUE,
            corner_radius=8,
        )
        panel.place(relx=0.5, rely=1.0, y=-42, anchor="s")
        self._a193_open_overlay = panel

        ctk.CTkLabel(
            panel,
            text="Åpner Resultatvisninger …",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
            text_color=theme.TEXT,
        ).pack(padx=18, pady=(10, 4))

        progress = ctk.CTkProgressBar(
            panel,
            width=260,
            mode="indeterminate",
        )
        progress.pack(fill="x", padx=18, pady=(0, 10))
        try:
            progress.start()
        except Exception:
            pass
        self._a193_open_progress = progress

        try:
            panel.lift()
            self.update_idletasks()
        except Exception:
            pass

    def _a192_end_open_indicator(self) -> None:
        progress = getattr(self, "_a193_open_progress", None)
        if progress is not None:
            try:
                progress.stop()
            except Exception:
                pass
        self._a193_open_progress = None

        panel = getattr(self, "_a193_open_overlay", None)
        if panel is not None:
            try:
                panel.destroy()
            except Exception:
                pass
        self._a193_open_overlay = None

        for button, previous_state in getattr(self, "_a193_disabled_depot_buttons", []) or []:
            try:
                if button.winfo_exists():
                    button.configure(state=previous_state)
            except Exception:
                pass
        self._a193_disabled_depot_buttons = []

        super()._a192_end_open_indicator()


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
