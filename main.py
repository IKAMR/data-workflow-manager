# a22 adds selective per-operation re-run on top of the established a21 runtime.
# Keep the established a20/a21 runtime boundary explicit for regression contracts.
from gui.persistent_app_a20 import WorkflowApp as _A20WorkflowApp
from gui.persistent_app_a21 import WorkflowApp as _A21WorkflowApp
from gui.persistent_app_a22 import run_gui


if __name__ == "__main__":
    run_gui()
