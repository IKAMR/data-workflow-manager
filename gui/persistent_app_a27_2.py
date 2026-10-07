from __future__ import annotations

from . import theme
from .persistent_app_a27_1 import WorkflowApp as A27_1WorkflowApp


class WorkflowApp(A27_1WorkflowApp):
    """v0.1.6-a27.2: Arkade CLI actions are reusable Noark 5 workflow operations."""


def run_gui() -> None:
    # Historical main.py entry point delegates to the current runtime.
    # v0.1.6 regression baseline was:
    # from .persistent_app_a39_runtime import WorkflowApp as CurrentWorkflowApp
    from .persistent_app_v017_a1 import WorkflowApp as CurrentWorkflowApp

    theme.apply_theme()
    app = CurrentWorkflowApp()
    app.mainloop()
