from __future__ import annotations

from settings import save_config

from .persistent_app_a19 import WorkflowApp as A19WorkflowApp
from .settings_dialog_a10 import SettingsDialog
from .window_geometry import capture_normal_geometry, startup_geometry


class WorkflowApp(A19WorkflowApp):
    """a10 runtime addition: safe and configurable main-window geometry restore."""

    def __init__(self) -> None:
        super().__init__()
        self._last_normal_window_geometry = capture_normal_geometry(self)
        self._restore_main_window_geometry()
        restored = capture_normal_geometry(self)
        if restored is not None:
            self._last_normal_window_geometry = restored

        self.bind("<Configure>", self._remember_main_window_geometry, add="+")
        self.bind("<Destroy>", self._persist_main_window_geometry, add="+")

    def _restore_main_window_geometry(self) -> None:
        geometry = startup_geometry(self.settings, self)
        if geometry:
            self.geometry(geometry)
            self.update_idletasks()

    def _remember_main_window_geometry(self, event=None) -> None:
        if event is not None and event.widget is not self:
            return
        geometry = capture_normal_geometry(self)
        if geometry is not None:
            self._last_normal_window_geometry = geometry

    def _persist_main_window_geometry(self, event=None) -> None:
        if event is not None and event.widget is not self:
            return
        geometry = self._last_normal_window_geometry
        if geometry is None:
            return
        values = {
            "main_window_x": geometry.x,
            "main_window_y": geometry.y,
            "main_window_width": geometry.width,
            "main_window_height": geometry.height,
        }
        self.settings.update(values)
        save_config(values)

    def _open_settings(self) -> None:
        SettingsDialog(self, self.settings, self._save_settings)


def run_gui() -> None:
    app = WorkflowApp()
    app.mainloop()
