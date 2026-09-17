from __future__ import annotations

import customtkinter as ctk

from . import theme
from .settings_dialog import SettingsDialog as BaseSettingsDialog


def _find_scrollable_frame(widget):
    """Find CustomTkinter's scrollable settings body through wrapper widgets."""
    if isinstance(widget, ctk.CTkScrollableFrame):
        return widget
    for child in widget.winfo_children():
        found = _find_scrollable_frame(child)
        if found is not None:
            return found
    return None


def _next_free_row(frame) -> int:
    """Return the first free grid row after all existing Setup content."""
    max_row = -1
    for child in frame.winfo_children():
        info = child.grid_info()
        if not info:
            continue
        try:
            row = int(info.get("row", -1))
        except (TypeError, ValueError):
            continue
        max_row = max(max_row, row)
    return max_row + 1


class SettingsDialog(BaseSettingsDialog):
    """a10 setup additions for independent main-window position and size restore."""

    def __init__(self, master, settings: dict, on_save):
        super().__init__(master, settings, on_save)

        self.restore_position_var = ctk.BooleanVar(
            value=bool(self.settings.get("restore_main_window_position", True))
        )
        self.restore_size_var = ctk.BooleanVar(
            value=bool(self.settings.get("restore_main_window_size", True))
        )

        body = _find_scrollable_frame(self)
        if body is None:
            return

        # Append the window section after ALL existing scrollable Setup content.
        # Do not move or re-grid any existing controls.
        row = _next_free_row(body)

        ctk.CTkLabel(
            body,
            text="Vindu",
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            padx=12,
            pady=(20, 8),
            sticky="w",
        )
        row += 1

        ctk.CTkCheckBox(
            body,
            text="Start med samme vindusposisjon",
            variable=self.restore_position_var,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            padx=12,
            pady=4,
            sticky="w",
        )
        row += 1

        ctk.CTkCheckBox(
            body,
            text="Start med samme vindusstørrelse",
            variable=self.restore_size_var,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            padx=12,
            pady=4,
            sticky="w",
        )
        row += 1

        ctk.CTkLabel(
            body,
            text=(
                "Lagret posisjon brukes bare når vinduet fortsatt er synlig "
                "på dagens skjermoppsett."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            padx=12,
            pady=(2, 16),
            sticky="w",
        )

    def _load_vars(self, settings: dict) -> None:
        super()._load_vars(settings)
        if hasattr(self, "restore_position_var"):
            self.restore_position_var.set(
                bool(settings.get("restore_main_window_position", True))
            )
            self.restore_size_var.set(
                bool(settings.get("restore_main_window_size", True))
            )

    def _collect(self) -> dict:
        updated = super()._collect()
        updated["restore_main_window_position"] = bool(
            self.restore_position_var.get()
        )
        updated["restore_main_window_size"] = bool(
            self.restore_size_var.get()
        )
        return updated
