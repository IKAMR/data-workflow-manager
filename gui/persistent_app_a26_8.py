from __future__ import annotations

from . import theme
from .persistent_app_a26_7 import WorkflowApp as A26_7WorkflowApp
from .settings_dialog_a26_8 import SettingsDialog


class WorkflowApp(A26_7WorkflowApp):
    """v0.1.6-a26.8: configurable, simplified Arkade output layout."""

    def _open_settings(self) -> None:
        SettingsDialog(self, self.settings, self._save_settings)


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
