from __future__ import annotations

from tkinter import messagebox

from noark5_workflow.job_batch_actions import (
    classify_arkade5_discovery_import_state,
    discover_arkade5_results_for_jobs,
    import_selected_arkade5_results,
)
from version import APP_NAME
from . import theme
from .arkade5_batch_discovery_dialog import Arkade5BatchDiscoveryDialog
from .persistent_app_a25_4 import WorkflowApp as A25_4WorkflowApp


class WorkflowApp(A25_4WorkflowApp):
    """v0.1.6-a25.6: render imported Arkade reports as fixed checked status."""

    def _a251_discover_arkade5_results(self, jobs) -> None:
        selected = tuple(jobs)
        if not selected:
            return

        self._a252_progress(
            f"Søker etter Arkade 5-resultater for {len(selected)} jobb(er) …"
        )
        result = discover_arkade5_results_for_jobs(
            selected,
            configured_roots=self._a251_configured_roots(self.settings),
            on_progress=self._a252_progress,
        )
        import_states = classify_arkade5_discovery_import_state(
            self.jobs.jobs(),
            result,
        )
        new_count = sum(row.status == "new" for row in import_states)
        already = sum(row.status == "already_imported" for row in import_states)
        self._a252_progress(
            f"Arkade 5: {result.reports_found} koblet, {new_count} nye, "
            f"{already} allerede importert"
        )

        dialog = Arkade5BatchDiscoveryDialog(
            self.jobs_window or self,
            result,
            import_states=import_states,
            on_accept=self._a255_import_arkade5_results,
        )
        dialog.focus()
        dialog.lift()

    def _a255_import_arkade5_results(self, selected):
        choices = tuple(selected)
        if not choices:
            return ()

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
            f"Importerer {len(choices)} nye Arkade 5-rapport(er) …"
        )
        result = import_selected_arkade5_results(
            self.jobs.jobs(),
            choices,
            imported_by=imported_by,
            on_progress=self._a252_progress,
        )

        imported_keys = {
            (row.job_id, str(candidate.sha256 or "").casefold())
            for job_id, candidate in choices
            for row in result.item_results
            if row.job_id == job_id
            and row.report_path == candidate.path
            and row.status in {"imported", "already_imported"}
        }

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
            f"Valgte nye rapporter: {result.selected_reports}",
            f"Berørte jobber: {result.selected_jobs}",
            f"Importert: {result.imported}",
            f"Allerede importert: {result.already_imported}",
            f"Feil: {result.failed}",
            f"PRONOM-evidens knyttet: {result.pronom_attached}",
            "",
            "Trefflisten er oppdatert. Importerte rapporter er nå merket «Allerede importert».",
        ]
        if result.pronom_failed:
            lines.insert(-2, f"PRONOM-tillegg med feil: {result.pronom_failed}")

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
        return tuple(imported_keys)


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
