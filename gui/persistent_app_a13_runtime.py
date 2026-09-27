from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from app.storage_layouts import suggest_storage_roles
from version import APP_NAME
from . import theme
from .persistent_app_a71 import WorkflowApp as A71WorkflowApp


_ROLE_LABELS = {
    "source_root": "Source - root",
    "source_tar": "Source - TAR",
    "source_unzipped": "Source - unpacked",
    "source_extraction": "Source - extraction",
    "work_root": "Work - root",
    "work_content": "Work - content",
    "work_operations": "Work - operations",
    "archive_root": "Storage - root",
}
_ROLE_ATTRS = tuple(_ROLE_LABELS)


class WorkflowApp(A71WorkflowApp):
    """a13 runtime hardening while preserving the established GUI."""

    def __init__(self) -> None:
        self._a13_jobs_window_opening = False
        super().__init__()

    def _open_jobs(self) -> None:
        existing = getattr(self, "jobs_window", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    try:
                        existing.focus_force()
                    except Exception:
                        existing.focus()
                    existing.refresh()
                    return
            except Exception:
                self.jobs_window = None

        if self._a13_jobs_window_opening:
            return
        self._a13_jobs_window_opening = True
        try:
            super()._open_jobs()
            self._bind_jobs_window_sync()
        finally:
            self._a13_jobs_window_opening = False


    def _bind_jobs_window_sync(self) -> None:
        """Keep Standard changes in Jobber visible in the main window immediately."""
        window = getattr(self, "jobs_window", None)
        if window is None or getattr(window, "_a13_main_sync_bound", False):
            return
        original = getattr(window, "_apply_standard_setup", None)
        if not callable(original):
            return

        def apply_standard_and_sync(job):
            original(job)
            if getattr(self, "current_job", None) is job:
                self._sync_active_job_to_main(job)

        window._apply_standard_setup = apply_standard_and_sync
        window._a13_main_sync_bound = True

    def _sync_active_job_to_main(self, job) -> None:
        """Mirror the authoritative Job object into the main-window controls."""
        self.current_job = job
        try:
            self._apply_profile(job.profile_id, persist=False)
        except Exception:
            pass
        self.workflow.clear()
        for operation_id in list(getattr(job, "workflow_ids", ()) or ()):
            self.workflow.add(operation_id)
        try:
            self._apply_job_operation_params(job)
        except Exception:
            pass
        self.workflow_panel.refresh()
        self._refresh_active_job_label()
        try:
            self._update_run_button()
        except Exception:
            pass

    def _source_browse_complete(self, path: Path) -> None:
        """Apply the same storage-role suggestion flow as the Mapper dialog.

        Selecting a new Source extraction from the main window must not leave
        Work/Storage roles pointing at the previous extraction.  Reuse the
        configured storage-layout profile and offer the same replace/keep
        choice that "Fyll ut forslag" gives in the Mapper dialog.
        """
        path = Path(path)
        job = self._ensure_job_for_current_source()
        if job is None:
            # A rapid Ny jobbliste -> Ny jobb -> Source sequence can leave the
            # visual job list showing JOB-001 while current_job has not yet
            # caught up. Recover only when the choice is unambiguous: exactly
            # one job exists. With several jobs we must never guess which job
            # the new Source belongs to.
            jobs = list(self.jobs.jobs()) if getattr(self, "jobs", None) is not None else []
            if len(jobs) == 1:
                job = jobs[0]
                self.current_job = job
                try:
                    self._refresh_active_job_label()
                except Exception:
                    pass
            else:
                messagebox.showwarning(
                    APP_NAME,
                    "Ingen aktiv jobb. Opprett eller åpne en jobb før Source kobles til jobben.",
                )
                return

        # _source_changed/_ensure_job_for_current_source has already attached
        # the concrete extraction path.  Build the complete role proposal from
        # that path, including Source root, Work and Storage.
        job.source_extraction = path
        layout_id = str(
            self.settings.get("storage_layout_profile", "ikamr_standard")
            or "none"
        )
        suggestions = suggest_storage_roles(
            source_root=getattr(job, "source_root", None),
            extraction_root=path,
            layout_id=layout_id,
        )

        values = {attr: getattr(job, attr, None) for attr in _ROLE_ATTRS}
        values["source_extraction"] = path

        empty_updates: list[tuple[str, Path]] = []
        conflicts: list[tuple[str, Path, Path]] = []
        for attr, suggested in suggestions.items():
            if attr not in values:
                continue
            suggested = Path(suggested)
            current = values[attr]
            if current is None:
                empty_updates.append((attr, suggested))
            elif Path(current) != suggested:
                conflicts.append((attr, Path(current), suggested))

        replace_conflicts = False
        if conflicts:
            lines = [
                "Noen eksisterende verdier avviker fra mappeprofilens forslag:",
                "",
            ]
            for attr, current, suggested in conflicts[:6]:
                lines.append(
                    f"{_ROLE_LABELS.get(attr, attr)}\n"
                    f"Nå: {current}\n"
                    f"Forslag: {suggested}"
                )
            if len(conflicts) > 6:
                lines.append(f"... og {len(conflicts) - 6} til")
            lines.extend(
                [
                    "",
                    "Ja = erstatt også avvikende eksisterende verdier.",
                    "Nei = fyll bare tomme felt og behold eksisterende verdier.",
                ]
            )
            replace_conflicts = messagebox.askyesno(
                "Fyll ut forslag",
                "\n".join(lines),
                parent=self,
            )

        for attr, suggested in empty_updates:
            values[attr] = suggested
        if replace_conflicts:
            for attr, _current, suggested in conflicts:
                values[attr] = suggested

        self._save_storage_roles(job, values)

    @staticmethod
    def _latest_storage_message(job) -> str:
        entries = list(getattr(job, "log_entries", ()) or ())
        for raw in reversed(entries[-160:]):
            text = str(raw)
            marker = "LAGRING UTILGJENGELIG"
            pos = text.find(marker)
            if pos >= 0:
                return text[pos:].strip()
        return ""

    def _execute_job(self, job, *, batch_mode: bool) -> bool:
        ok = super()._execute_job(job, batch_mode=batch_mode)
        if not ok:
            storage_message = self._latest_storage_message(job)
            if storage_message:
                job.message = storage_message
                try:
                    if self.job_list_path is not None:
                        self._write_job_list(self.job_list_path)
                except Exception:
                    pass
                try:
                    self.status_bar.set_status(storage_message)
                except Exception:
                    pass
                jobs_window = getattr(self, "jobs_window", None)
                if jobs_window is not None:
                    try:
                        if jobs_window.winfo_exists():
                            self.after(0, jobs_window.refresh)
                    except Exception:
                        pass
        return ok


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
