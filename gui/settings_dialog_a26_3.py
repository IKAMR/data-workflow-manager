from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from noark5_workflow.external_tools.arkade5 import inspect_arkade5_cli
from . import theme
from .settings_dialog import SettingsDialog as BaseSettingsDialog


class SettingsDialog(BaseSettingsDialog):
    """a26.3: configure and inspect Arkade 5 CLI without hardcoded install paths."""

    def __init__(self, master, settings: dict, on_save):
        super().__init__(master, settings, on_save)
        self.arkade5_cli_var = ctk.StringVar(
            value=str(self.settings.get("arkade5_cli_path", "") or "")
        )
        self.arkade5_cli_status_var = ctk.StringVar(value="Ikke kontrollert")
        self._a263_append_arkade5_setup()

    def _a263_find_scrollable_body(self, widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkScrollableFrame):
                return child
            nested = self._a263_find_scrollable_body(child)
            if nested is not None:
                return nested
        return None

    @staticmethod
    def _a263_next_grid_row(body) -> int:
        rows = []
        for child in body.winfo_children():
            try:
                info = child.grid_info()
                if info and "row" in info:
                    rows.append(int(info["row"]))
            except Exception:
                pass
        return (max(rows) + 1) if rows else 0

    def _a263_append_arkade5_setup(self) -> None:
        body = self._a263_find_scrollable_body(self)
        if body is None:
            return
        body.grid_columnconfigure(1, weight=1)
        row = self._a263_next_grid_row(body)

        ctk.CTkLabel(
            body,
            text="Eksterne verktøy",
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(20, 8), sticky="w")

        row += 1
        ctk.CTkLabel(
            body,
            text="Arkade 5 CLI",
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=row, column=0, padx=12, pady=8, sticky="w")

        tools = ctk.CTkFrame(body, fg_color="transparent")
        tools.grid(row=row, column=1, padx=12, pady=8, sticky="ew")
        tools.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(
            tools,
            textvariable=self.arkade5_cli_var,
            font=theme.font(theme.NORMAL_SIZE),
            placeholder_text="Arkivverket.Arkade.CLI.exe",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            tools,
            text="Velg…",
            width=68,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._a263_browse_arkade5_cli,
        ).grid(row=0, column=1, padx=(6, 4))
        ctk.CTkButton(
            tools,
            text="Kontroller",
            width=90,
            command=self._a263_check_arkade5_cli,
        ).grid(row=0, column=2)

        row += 1
        ctk.CTkLabel(
            body,
            textvariable=self.arkade5_cli_status_var,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
            justify="left",
        ).grid(row=row, column=1, padx=12, pady=(0, 12), sticky="ew")

    def _a263_browse_arkade5_cli(self) -> None:
        current = self.arkade5_cli_var.get().strip()
        initialdir = None
        if current:
            try:
                parent = Path(current).parent
                if parent.is_dir():
                    initialdir = str(parent)
            except OSError:
                pass
        kwargs = {
            "title": "Velg Arkade 5 CLI",
            "filetypes": [
                ("Arkade 5 CLI", "Arkivverket.Arkade.CLI.exe"),
                ("Programfiler", "*.exe"),
                ("Alle filer", "*.*"),
            ],
        }
        if initialdir:
            kwargs["initialdir"] = initialdir
        filename = filedialog.askopenfilename(**kwargs)
        if filename:
            self.arkade5_cli_var.set(filename)
            self.arkade5_cli_status_var.set("Ikke kontrollert")

    def _a263_check_arkade5_cli(self) -> None:
        value = self.arkade5_cli_var.get().strip()
        self.arkade5_cli_status_var.set("Kontrollerer Arkade 5 CLI …")
        self.update_idletasks()
        status = inspect_arkade5_cli(value)
        self.arkade5_cli_status_var.set(status.message)

    def _collect(self) -> dict:
        updated = super()._collect()
        updated["arkade5_cli_path"] = self.arkade5_cli_var.get().strip()
        return updated

    def _load_vars(self, settings: dict) -> None:
        super()._load_vars(settings)
        if hasattr(self, "arkade5_cli_var"):
            self.arkade5_cli_var.set(str(settings.get("arkade5_cli_path", "") or ""))
            self.arkade5_cli_status_var.set("Ikke kontrollert")
