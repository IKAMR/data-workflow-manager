from __future__ import annotations

from . import theme
from .persistent_app_a18_5 import WorkflowApp as A18_5WorkflowApp


class WorkflowApp(A18_5WorkflowApp):
    """v0.1.6-a18.6: preserve a18.5 result context with corrected runtime-chain tests."""


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
