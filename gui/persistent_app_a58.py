
from __future__ import annotations

from . import theme
from .persistent_app_a57 import WorkflowApp as A57WorkflowApp


class WorkflowApp(A57WorkflowApp):
    """v0.1.5-a23: adaptive status bar prioritising runtime context."""

    def __init__(self) -> None:
        super().__init__()
        self.after_idle(self._refresh_adaptive_status_bar)

    def _refresh_adaptive_status_bar(self) -> None:
        try:
            width = max(1, int(self.status_bar.winfo_width()))
            self.status_bar._display_mode = self.status_bar._mode_for_width(width)
            self.status_bar._refresh_all()
        except Exception:
            pass


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
