from __future__ import annotations

from . import theme
from .persistent_app_a15_1 import WorkflowApp as A15_1WorkflowApp


class WorkflowApp(A15_1WorkflowApp):
    """v0.1.6-a16.1: complete 2026 XPath result materialization."""


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
