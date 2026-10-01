from __future__ import annotations

import customtkinter as ctk

from . import theme
from .settings_dialog_a26_3 import SettingsDialog as A26_3SettingsDialog


class SettingsDialog(A26_3SettingsDialog):
    """a26.8: configurable Arkade output subfolder below Work - operations."""

    def __init__(self, master, settings: dict, on_save):
        super().__init__(master, settings, on_save)
        self.arkade5_output_subfolder_var = ctk.StringVar(
            value=str(settings.get("arkade5_output_subfolder", "arkade5_<ver>") or "arkade5_<ver>")
        )
        self._a268_append_output_subfolder()

    def _a268_append_output_subfolder(self) -> None:
        body = self._a263_find_scrollable_body(self)
        if body is None:
            return
        row = self._a263_next_grid_row(body)

        ctk.CTkLabel(
            body,
            text="Arkade 5 output-undermappe",
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkEntry(
            body,
            textvariable=self.arkade5_output_subfolder_var,
            font=theme.font(theme.NORMAL_SIZE),
            placeholder_text="arkade5_<ver>",
        ).grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(
            body,
            text=(
                "Relativ undermappe under Work - operations. <ver> erstattes med "
                "oppdaget versjon, f.eks. arkade5_<ver> → arkade5_v2.13.1."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=760,
        ).grid(row=row, column=1, padx=12, pady=(0, 12), sticky="ew")

    def _collect(self) -> dict:
        updated = super()._collect()
        updated["arkade5_output_subfolder"] = (
            self.arkade5_output_subfolder_var.get().strip() or "arkade5_<ver>"
        )
        return updated

    def _load_vars(self, settings: dict) -> None:
        super()._load_vars(settings)
        if hasattr(self, "arkade5_output_subfolder_var"):
            self.arkade5_output_subfolder_var.set(
                str(settings.get("arkade5_output_subfolder", "arkade5_<ver>") or "arkade5_<ver>")
            )
