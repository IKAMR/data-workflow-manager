from __future__ import annotations

from . import theme
from .persistent_app_a26_2 import WorkflowApp as A26_2WorkflowApp
from .settings_dialog_a26_3 import SettingsDialog


class WorkflowApp(A26_2WorkflowApp):
    """v0.1.6-a26.3: Arkade 5 CLI setup and version inspection."""

    def _open_settings(self) -> None:
        SettingsDialog(self, self.settings, self._save_settings)


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
