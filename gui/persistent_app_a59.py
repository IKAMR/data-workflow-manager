
from __future__ import annotations

from . import theme
from .persistent_app_a58 import WorkflowApp as A58WorkflowApp


class WorkflowApp(A58WorkflowApp):
    """v0.1.5-a24: usable main window on smaller desktop clients.

    The Source inventory and workflow operation list are the areas allowed to
    shrink/scroll. Fixed workflow/job-list controls remain reachable.
    """

    MIN_WIDTH = 960
    MIN_HEIGHT = 560

    def __init__(self) -> None:
        super().__init__()

        # Logical Tk pixels. Kept below the 1280x720 physical target so
        # ordinary Windows display scaling does not make smaller clients
        # unusable.
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)

        # Critical a24 fix:
        # prevent SourcePanel and WorkflowPanel from forcing their requested
        # heights onto the left column. Their internal scrollable/text areas
        # may shrink instead, keeping the fixed buttons reachable.
        try:
            self.source_panel.grid_propagate(False)
        except Exception:
            pass
        try:
            self.workflow_panel.grid_propagate(False)
        except Exception:
            pass

        self._a24_resize_after = None
        self.bind("<Configure>", self._a24_schedule_layout, add="+")
        self.after_idle(self._a24_apply_layout)

    def _a24_schedule_layout(self, event=None) -> None:
        if event is not None and getattr(event, "widget", None) is not self:
            return
        pending = self._a24_resize_after
        if pending is not None:
            try:
                self.after_cancel(pending)
            except Exception:
                pass
        self._a24_resize_after = self.after(60, self._a24_apply_layout)

    @staticmethod
    def _a24_source_height(window_height: int) -> int:
        """Reserve vertical room for the fixed workflow controls first."""
        if window_height < 620:
            return 150
        if window_height < 700:
            return 180
        if window_height < 800:
            return 220
        if window_height < 900:
            return 280
        return 360

    def _a24_apply_layout(self) -> None:
        self._a24_resize_after = None
        try:
            width = max(1, int(self.winfo_width()))
            height = max(1, int(self.winfo_height()))
        except Exception:
            return

        # Width: the left column yields some width before the main work area.
        if width < 1100:
            left_width = 320
        elif width < 1280:
            left_width = 350
        else:
            left_width = theme.LEFT_WIDTH

        try:
            left = self.source_panel.master
            left.configure(width=left_width)
        except Exception:
            pass

        # Height: constrain the entire SourcePanel, not only the textbox.
        # The Source textbox can scroll internally. This is what actually frees
        # room for the workflow panel and its fixed lower action buttons.
        source_height = self._a24_source_height(height)
        try:
            self.source_panel.configure(height=source_height)
        except Exception:
            pass

        # Give the Source textbox the remaining interior height. CTkTextbox is
        # scrollable, so inventory remains available even when visually short.
        try:
            info_height = max(60, source_height - 125)
            self.source_panel.info.configure(height=info_height)
        except Exception:
            pass

        # WorkflowPanel.items is already a CTkScrollableFrame. With propagation
        # disabled on the outer panel, its operation list shrinks and scrolls
        # while Kjør workflow / profile / job-list actions remain visible.
        try:
            self.workflow_panel.update_idletasks()
        except Exception:
            pass

        try:
            self.status_bar._display_mode = self.status_bar._mode_for_width(width)
            self.status_bar._refresh_all()
        except Exception:
            pass


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
