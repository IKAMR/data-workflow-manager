# a21 adds a11 Source / Work / Storage setup on top of the established a20
# runtime boundary (window geometry and the a19 persistence chain).
from gui.persistent_app_a20 import WorkflowApp as _A20WorkflowApp
from gui.persistent_app_a21 import run_gui


if __name__ == "__main__":
    run_gui()
