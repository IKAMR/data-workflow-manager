from __future__ import annotations

from noark5_workflow.core.job_runner_a39 import A39JobRunner
from .persistent_app_a38_runtime import WorkflowApp as A38WorkflowApp


class WorkflowApp(A38WorkflowApp):
    """v0.1.6-a39: continue Noark 5 workflow after XSD validation findings."""

    def __init__(self) -> None:
        super().__init__()
        self.job_runner = A39JobRunner(
            self.registry,
            self.executor,
            self.settings,
        )
