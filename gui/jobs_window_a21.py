
from __future__ import annotations

from tkinter import StringVar, messagebox

import customtkinter as ctk

from version import APP_NAME
from . import theme
from .jobs_window_a20 import A20JobsWindow


_MODE_LABELS = {
    "auto": "Auto",
    "sequential": "Sekvensiell",
    "parallel": "Parallell",
}
_MODE_VALUES = {label: value for value, label in _MODE_LABELS.items()}


class A21JobsWindow(A20JobsWindow):
    """Data Workflow Manager a5: batch parallelism controls at job-list level."""

    def __init__(
        self,
        *args,
        get_batch_execution_config=None,
        set_batch_execution_config=None,
        **kwargs,
    ) -> None:
        self.get_batch_execution_config = (
            get_batch_execution_config
            or (lambda: {"mode": "auto", "max_workers": 0})
        )
        self.set_batch_execution_config = (
            set_batch_execution_config
            or (lambda _mode, _workers: (True, ""))
        )
        super().__init__(*args, **kwargs)

        # A20 uses row 4 for Work subfolder rule and row 5 for summary.
        # Insert batch execution controls before the summary.
        self.summary.grid(row=6, column=0, padx=18, pady=(2, 14), sticky="w")
        self.grid_rowconfigure(5, weight=0)

        frame = ctk.CTkFrame(self, fg_color=theme.PANEL_BG_DARK, corner_radius=8)
        frame.grid(row=5, column=0, padx=18, pady=(0, 8), sticky="ew")
        frame.grid_columnconfigure(4, weight=1)

        cfg = self.get_batch_execution_config() or {}
        mode = str(cfg.get("mode", "auto") or "auto")
        max_workers = int(cfg.get("max_workers", 0) or 0)

        ctk.CTkLabel(
            frame,
            text="Batchkjøring",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
        ).grid(row=0, column=0, padx=(12, 8), pady=8, sticky="w")

        self.batch_mode_var = StringVar(value=_MODE_LABELS.get(mode, "Auto"))
        ctk.CTkOptionMenu(
            frame,
            variable=self.batch_mode_var,
            values=list(_MODE_LABELS.values()),
            width=130,
        ).grid(row=0, column=1, padx=6, pady=8, sticky="w")

        ctk.CTkLabel(
            frame,
            text="Maks workers",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_SUB,
        ).grid(row=0, column=2, padx=(14, 6), pady=8, sticky="w")

        self.max_workers_var = StringVar(
            value="Auto" if max_workers <= 0 else str(max_workers)
        )
        ctk.CTkOptionMenu(
            frame,
            variable=self.max_workers_var,
            values=["Auto", "1", "2", "3", "4", "6", "8"],
            width=90,
        ).grid(row=0, column=3, padx=6, pady=8, sticky="w")

        ctk.CTkButton(
            frame,
            text="Bruk",
            width=72,
            command=self._apply_batch_execution_config,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=5, padx=(8, 12), pady=8)

        ctk.CTkLabel(
            frame,
            text=(
                "Auto vurderer CPU, ledig RAM, filstørrelse og lagringstype. "
                "Workflow inne i hver jobb er fortsatt sekvensiell."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, columnspan=6, padx=12, pady=(0, 8), sticky="ew")

    def _apply_batch_execution_config(self) -> None:
        mode = _MODE_VALUES.get(self.batch_mode_var.get(), "auto")
        raw_workers = self.max_workers_var.get().strip()
        max_workers = 0 if raw_workers == "Auto" else int(raw_workers)

        ok, message = self.set_batch_execution_config(mode, max_workers)
        if not ok:
            messagebox.showerror(APP_NAME, message)
            return

        cfg = self.get_batch_execution_config() or {}
        mode = str(cfg.get("mode", "auto") or "auto")
        max_workers = int(cfg.get("max_workers", 0) or 0)
        self.batch_mode_var.set(_MODE_LABELS.get(mode, "Auto"))
        self.max_workers_var.set("Auto" if max_workers <= 0 else str(max_workers))
