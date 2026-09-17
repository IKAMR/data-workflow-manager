# a20 adds configurable/safe main-window geometry restore on top of a19.
# Keep the a19 import explicit as the established runtime compatibility boundary.
from gui.persistent_app_a19 import WorkflowApp as _A19WorkflowApp
from gui.persistent_app_a20 import run_gui


if __name__ == "__main__":
    run_gui()
