from __future__ import annotations

from .jobs_window_v017_a1 import V017A1JobsWindow


class V017A2JobsWindow(V017A1JobsWindow):
    """v0.1.7-a2: job list remains for actions that support selected job sets.

    KDRS Query import is intentionally not exposed here because it belongs to
    exactly one active extraction/job and is available from the main job view.
    """
