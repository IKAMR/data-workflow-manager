"""Small a4.6 GUI regressions fix over the committed v0.1.7 runtime."""
from __future__ import annotations

import customtkinter as ctk

from .persistent_app_v017_a2 import WorkflowApp as V017A2WorkflowApp


class WorkflowApp(V017A2WorkflowApp):
    def __init__(self):
        super().__init__()
        # The bottom resize handle has both top and bottom blue border lines.
        # Remove its border while retaining the draggable handle itself.
        splitter = getattr(self, "bottom_splitter", None)
        if splitter is not None:
            splitter.configure(border_width=0)
        self.after_idle(self._v017_arrange_log_actions)

    def _v017_arrange_log_actions(self) -> None:
        """Regrid all header actions once, rather than swapping occupied cells."""
        header = getattr(getattr(self, "log_panel", None), "header", None)
        if header is None:
            return
        found = {}
        for child in header.winfo_children():
            if isinstance(child, ctk.CTkButton):
                label = str(child.cget("text"))
                if label in {"Resultater", "Råresultater", "Depotvurdering", "Tøm"}:
                    found[label] = child
        raw = found.get("Råresultater") or found.get("Resultater")
        depot = found.get("Depotvurdering")
        clear = found.get("Tøm")
        if raw is not None:
            raw.configure(text="Råresultater", width=92)
        for widget in (raw, depot, clear):
            if widget is not None and widget.grid_info():
                widget.grid_remove()
        for column, widget in ((1, depot), (2, raw), (3, clear)):
            if widget is not None:
                widget.grid(row=0, column=column, padx=(4, 0), pady=0, sticky="e")
        header.grid_columnconfigure(0, weight=1)
        for column in range(1, 4):
            header.grid_columnconfigure(column, weight=0)
