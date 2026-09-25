from __future__ import annotations

from . import theme
from .persistent_app_a71 import WorkflowApp as A71WorkflowApp
from .window_placement import install_native_dialog_policy


class WorkflowApp(A71WorkflowApp):
    """v0.1.6-a12: normal native desktop controls for all app dialogs."""

    def __init__(self) -> None:
        install_native_dialog_policy()
        super().__init__()


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
