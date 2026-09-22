from __future__ import annotations

from . import theme
from .jobs_window_a26 import A26JobsWindow


_MODE_LABELS = {
    "auto": "Auto",
    "sequential": "Sekvensiell",
    "parallel": "Parallell",
}


class A27JobsWindow(A26JobsWindow):
    """a9: clearer execution wording in the Jobs window."""

    def set_batch_running(self, running: bool) -> None:
        super().set_batch_running(running)

        cfg = self.get_batch_execution_config() or {}
        mode = str(cfg.get("mode", "auto") or "auto").lower()
        label = _MODE_LABELS.get(mode, mode)

        if running:
            text = f"Kjøremodus: {label} – KJØRER   |   Worker: Lokal (denne PC-en)"
            color = theme.BLUE
        else:
            text = f"Kjøremodus: {label}   |   Worker: Lokal (denne PC-en)"
            color = theme.TEXT_MUTED

        self.scheduler_label.configure(text=text, text_color=color)
