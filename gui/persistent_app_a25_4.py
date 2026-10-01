from __future__ import annotations

from tkinter import messagebox

from noark5_workflow.job_batch_actions import import_selected_arkade5_results
from version import APP_NAME
from . import theme
from .persistent_app_a25_3 import WorkflowApp as A25_3WorkflowApp


class WorkflowApp(A25_3WorkflowApp):
    """v0.1.6-a25.4: import explicitly selected Arkade 5 reports per job."""

    def _a253_accept_arkade5_results(self, selected) -> None:
        choices = tuple(selected)
        if not choices:
            return

        imported_by = {}
        try:
            identity = self.current_user_identity() or {}
            for key in ("user_id", "username", "name", "email"):
                value = str(identity.get(key) or "").strip()
                if value:
                    imported_by[key] = value
        except Exception:
            pass

        self._a252_progress(
            f"Importerer {len(choices)} valgte Arkade 5-rapport(er) …"
        )
        result = import_selected_arkade5_results(
            self.jobs.jobs(),
            choices,
            imported_by=imported_by,
            on_progress=self._a252_progress,
        )

        try:
            self.status_bar.set_status(
                f"Arkade 5: {result.imported} importert, "
                f"{result.already_imported} allerede importert, {result.failed} feil"
            )
        except Exception:
            pass

        lines = [
            "Arkade 5-resultater er behandlet.",
            "",
            f"Valgte rapporter: {result.selected_reports}",
            f"Berørte jobber: {result.selected_jobs}",
            f"Importert: {result.imported}",
            f"Allerede importert: {result.already_imported}",
            f"Feil: {result.failed}",
            f"PRONOM-evidens knyttet: {result.pronom_attached}",
        ]
        if result.pronom_failed:
            lines.append(f"PRONOM-tillegg med feil: {result.pronom_failed}")

        failures = [row for row in result.item_results if row.status == "failed"]
        if failures:
            lines.extend(["", "Feil:"])
            for row in failures[:5]:
                lines.append(f"{row.job_id}: {row.error}")
            if len(failures) > 5:
                lines.append(f"… og {len(failures) - 5} til")

        messagebox.showinfo(
            APP_NAME,
            "\n".join(lines),
            parent=self.jobs_window,
        )


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
