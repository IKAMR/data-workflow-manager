from __future__ import annotations

import customtkinter as ctk

from version import APP_NAME
from . import theme
from .jobs_window_a24 import A24JobsWindow


_MODE_LABELS = {
    "auto": "Auto",
    "sequential": "Sekvensiell",
    "parallel": "Parallell",
}


class A25JobsWindow(A24JobsWindow):
    """a7: final polish of the job-list interaction model."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.title(f"Jobber - {APP_NAME}")
        self._refresh_job_window_explanation()
        self.set_batch_running(self._batch_running)

    def _refresh_job_window_explanation(self) -> None:
        """Remove the obsolete claim that Start alle is always sequential."""
        for child in self.winfo_children():
            if not isinstance(child, ctk.CTkFrame):
                continue
            for nested in child.winfo_children():
                if not isinstance(nested, ctk.CTkLabel):
                    continue
                try:
                    text = str(nested.cget("text"))
                except Exception:
                    continue
                if text.startswith("Persistent jobbliste."):
                    nested.configure(
                        text=(
                            "Persistent jobbliste. Batchkjøring følger valgt "
                            "strategi: Auto, Sekvensiell eller Parallell."
                        )
                    )
                    return

    def set_batch_running(self, running: bool) -> None:
        super().set_batch_running(running)

        if running:
            text = "Scheduler: KJØRER batch   |   Worker: Lokal (denne PC-en)"
            color = theme.BLUE
        else:
            cfg = self.get_batch_execution_config() or {}
            mode = str(cfg.get("mode", "auto") or "auto").lower()
            label = _MODE_LABELS.get(mode, mode)
            text = f"Scheduler: {label}   |   Worker: Lokal (denne PC-en)"
            color = theme.TEXT_MUTED

        self.scheduler_label.configure(text=text, text_color=color)
