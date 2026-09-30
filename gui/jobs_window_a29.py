from __future__ import annotations

from pathlib import Path
import threading
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from noark5_workflow.noark5_discovery import (
    Noark5DiscoveryResult,
    discover_noark5_extractions,
)
from settings import save_config
from version import APP_NAME
from . import theme
from .jobs_window_a28 import A28JobsWindow


class A29JobsWindow(A28JobsWindow):
    """a24.1: recursive Noark 5 discovery beside ordinary job creation."""

    def __init__(
        self,
        *args,
        on_noark5_discovery: Callable[[Noark5DiscoveryResult], None] | None = None,
        **kwargs,
    ) -> None:
        self.on_noark5_discovery = on_noark5_discovery or (lambda _result: None)
        self._noark5_discovery_running = False
        super().__init__(*args, **kwargs)
        self._install_noark5_discovery_action()

    def _install_noark5_discovery_action(self) -> None:
        parent = self.new_button.master
        self.noark5_discovery_button = ctk.CTkButton(
            parent,
            text="Finn Noark 5...",
            command=self._choose_noark5_discovery_root,
            width=118,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self.noark5_discovery_button.pack(
            side="left",
            padx=(0, 8),
            before=self.start_all_button,
        )

    def _choose_noark5_discovery_root(self) -> None:
        if self._batch_running or self._noark5_discovery_running:
            return

        kwargs = {"title": "Velg startmappe for søk etter Noark 5-uttrekk"}
        previous = str(self.settings.get("last_noark5_discovery_root", "")).strip()
        if previous and Path(previous).is_dir():
            kwargs["initialdir"] = previous

        folder = filedialog.askdirectory(**kwargs)
        if not folder:
            return

        save_config({"last_noark5_discovery_root": folder})
        self.settings["last_noark5_discovery_root"] = folder
        self._start_noark5_discovery(Path(folder))

    def _start_noark5_discovery(self, start_root: Path) -> None:
        self._noark5_discovery_running = True
        self.noark5_discovery_button.configure(text="Søker...", state="disabled")

        def worker() -> None:
            try:
                result = discover_noark5_extractions(start_root)
                error = None
            except Exception as exc:  # GUI boundary: report filesystem errors cleanly.
                result = None
                error = exc

            def finish() -> None:
                self._noark5_discovery_running = False
                try:
                    self.noark5_discovery_button.configure(
                        text="Finn Noark 5...",
                        state="disabled" if self._batch_running else "normal",
                    )
                except Exception:
                    return

                if error is not None:
                    messagebox.showerror(
                        APP_NAME,
                        f"Søket etter Noark 5-uttrekk feilet.\n\n{error}",
                        parent=self,
                    )
                    return

                if result is not None:
                    self.on_noark5_discovery(result)
                    self.refresh()

            try:
                self.after(0, finish)
            except Exception:
                pass

        threading.Thread(
            target=worker,
            name="noark5-discovery",
            daemon=True,
        ).start()

    def set_batch_running(self, running: bool) -> None:
        super().set_batch_running(running)
        if hasattr(self, "noark5_discovery_button"):
            enabled = not running and not self._noark5_discovery_running
            self.noark5_discovery_button.configure(
                state="normal" if enabled else "disabled"
            )
