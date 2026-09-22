from __future__ import annotations

from pathlib import Path

from . import theme
from .noark5_control_overview_dialog import Noark5ControlOverviewDialog
from .persistent_app_a41 import WorkflowApp as A41WorkflowApp


class WorkflowApp(A41WorkflowApp):
    """v0.1.4-a10: in-app Noark 5 control worklist."""

    def __init__(self) -> None:
        super().__init__()
        self._control_overview_dialog = None

    def _latest_validation_overview_json_path(self) -> Path | None:
        html_path = self._latest_validation_overview_path()
        if html_path is None:
            return None
        json_path = html_path.with_suffix(".json")
        return json_path if json_path.is_file() else None

    def _open_validation_overview(self) -> None:
        html_path = self._latest_validation_overview_path()
        json_path = self._latest_validation_overview_json_path()
        if html_path is None or json_path is None:
            self.status_bar.set_status("Ingen komplett Noark 5 kontrolloversikt er generert ennå")
            return

        existing = self._control_overview_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.destroy()
            except Exception:
                pass

        parent = self
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    parent = self.jobs_window
            except Exception:
                pass

        dialog = Noark5ControlOverviewDialog(
            parent,
            overview_json=json_path,
            overview_html=html_path,
        )
        self._control_overview_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._control_overview_closed(event, d),
            add="+",
        )

        # Kontrolloversikten åpnes fra Jobber-vinduet og skal derfor ligge
        # foran dette vinduet. Den er bevisst ikke modal; brukeren kan fortsatt
        # sammenligne med Jobber-vinduet ved behov.
        try:
            dialog.update_idletasks()
            dialog.lift()
            dialog.focus_force()
            dialog.after_idle(dialog.lift)
        except Exception:
            pass

        self.status_bar.set_status(f"Åpnet kontrolloversikt: {html_path.name}")

    def _control_overview_closed(self, event, dialog) -> None:
        if event.widget is dialog and self._control_overview_dialog is dialog:
            self._control_overview_dialog = None


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
