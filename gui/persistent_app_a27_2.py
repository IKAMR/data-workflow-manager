from __future__ import annotations

from . import theme
from .persistent_app_a27_1 import WorkflowApp as A27_1WorkflowApp


class WorkflowApp(A27_1WorkflowApp):
    """v0.1.6-a27.2: Arkade CLI actions are reusable Noark 5 workflow operations."""


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
