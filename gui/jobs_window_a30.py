from __future__ import annotations

from pathlib import Path
import threading
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from noark5_workflow.extraction_discovery import (
    ExtractionDiscoveryResult,
    extraction_definition,
    load_extraction_definitions,
    discover_from_lists,
    discover_in_folders,
)
from settings import save_config
from version import APP_NAME
from . import theme
from .extraction_discovery_dialog import ExtractionDiscoveryDialog
from .jobs_window_a29 import A29JobsWindow


class A30JobsWindow(A29JobsWindow):
    """a24.2: generic, definition-driven extraction discovery."""

    def __init__(
        self,
        *args,
        on_extraction_discovery: Callable[[ExtractionDiscoveryResult], None] | None = None,
        **kwargs,
    ) -> None:
        self.on_extraction_discovery = on_extraction_discovery or (lambda _result: None)
        self._extraction_discovery_running = False
        self._extraction_definitions = load_extraction_definitions()
        super().__init__(*args, **kwargs)
        self._replace_specialized_discovery_actions()

    def _replace_specialized_discovery_actions(self) -> None:
        # a17 and a24.1 both added specialized discovery buttons. Keep their
        # implementation for compatibility, but expose one generic entry point.
        for name in ("discover_button", "noark5_discovery_button"):
            widget = getattr(self, name, None)
            if widget is not None:
                try:
                    widget.pack_forget()
                except Exception:
                    pass

        parent = self.new_button.master
        self.extraction_discovery_button = ctk.CTkButton(
            parent,
            text="Finn uttrekk...",
            command=self._open_extraction_discovery,
            width=118,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self.extraction_discovery_button.pack(
            side="left",
            padx=(0, 8),
            before=self.start_all_button,
        )

    def _open_extraction_discovery(self) -> None:
        if self._batch_running or self._extraction_discovery_running:
            return
        initial = str(self.settings.get("last_extraction_discovery_type", "") or "")
        ExtractionDiscoveryDialog(
            self,
            self._extraction_definitions,
            initial_type_id=initial,
            on_folders=self._choose_folder_source,
            on_lists=self._choose_list_source,
        )

    def _remember_type(self, type_id: str) -> None:
        self.settings["last_extraction_discovery_type"] = type_id
        save_config({"last_extraction_discovery_type": type_id})

    def _choose_folder_source(self, type_id: str) -> None:
        definition = extraction_definition(type_id, self._extraction_definitions)
        self._remember_type(type_id)
        kwargs = {"title": f"Velg startmappe for søk etter {definition.label}-uttrekk"}
        previous = str(self.settings.get("last_extraction_discovery_root", "") or "").strip()
        if previous and Path(previous).is_dir():
            kwargs["initialdir"] = previous
        folder = filedialog.askdirectory(**kwargs)
        if not folder:
            return
        self.settings["last_extraction_discovery_root"] = folder
        save_config({"last_extraction_discovery_root": folder})
        self._start_discovery(
            definition.label,
            lambda: discover_in_folders(Path(folder), definition),
        )

    def _choose_list_source(self, type_id: str) -> None:
        definition = extraction_definition(type_id, self._extraction_definitions)
        self._remember_type(type_id)
        kwargs = {
            "title": f"Velg listegrunnlag for {definition.label}-uttrekk",
            "filetypes": [
                ("Lister og logger", "*.log *.txt"),
                ("Loggfiler", "*.log"),
                ("Tekstfiler", "*.txt"),
                ("Alle filer", "*.*"),
            ],
        }
        previous = str(self.settings.get("last_extraction_discovery_list_dir", "") or "").strip()
        if previous and Path(previous).is_dir():
            kwargs["initialdir"] = previous
        selected = filedialog.askopenfilenames(**kwargs)
        if not selected:
            return
        paths = tuple(Path(value) for value in selected)
        self.settings["last_extraction_discovery_list_dir"] = str(paths[0].parent)
        save_config({"last_extraction_discovery_list_dir": str(paths[0].parent)})
        self._start_discovery(
            definition.label,
            lambda: discover_from_lists(paths, definition),
        )

    def _start_discovery(self, label: str, callback) -> None:
        self._extraction_discovery_running = True
        self.extraction_discovery_button.configure(text="Søker...", state="disabled")

        def worker() -> None:
            try:
                result = callback()
                error = None
            except Exception as exc:
                result = None
                error = exc

            def finish() -> None:
                self._extraction_discovery_running = False
                try:
                    self.extraction_discovery_button.configure(
                        text="Finn uttrekk...",
                        state="disabled" if self._batch_running else "normal",
                    )
                except Exception:
                    return
                if error is not None:
                    messagebox.showerror(
                        APP_NAME,
                        f"Søket etter {label}-uttrekk feilet.\n\n{error}",
                        parent=self,
                    )
                    return
                if result is not None:
                    self.on_extraction_discovery(result)
                    self.refresh()

            try:
                self.after(0, finish)
            except Exception:
                pass

        threading.Thread(target=worker, name="extraction-discovery", daemon=True).start()

    def set_batch_running(self, running: bool) -> None:
        super().set_batch_running(running)
        if hasattr(self, "extraction_discovery_button"):
            enabled = not running and not self._extraction_discovery_running
            self.extraction_discovery_button.configure(
                state="normal" if enabled else "disabled"
            )
