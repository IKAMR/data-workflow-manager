from __future__ import annotations

from . import theme
from .persistent_app_a27_1 import WorkflowApp as A27_1WorkflowApp


class WorkflowApp(A27_1WorkflowApp):
    """v0.1.6-a27.2: Arkade CLI actions are reusable Noark 5 workflow operations."""


def run_gui() -> None:
    # a27.2 remains the final historical entry point in main.py.
    # From a37 it delegates to the current runtime so the long import chain
    # cannot silently override the newest implementation.
    from .persistent_app_a37_runtime import WorkflowApp as CurrentWorkflowApp

    theme.apply_theme()
    app = CurrentWorkflowApp()
    app.mainloop()
