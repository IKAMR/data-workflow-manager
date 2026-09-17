from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from . import theme
from .depot_assessment_dialog import DepotAssessmentDialog
from .persistent_app_a18 import WorkflowApp as A18WorkflowApp


class WorkflowApp(A18WorkflowApp):
    """a19 runtime layer: GUI access to persistent depot assessment."""

    def __init__(self) -> None:
        self._depot_assessment_dialog = None
        super().__init__()
        self._install_depot_assessment_action()
        self._install_persistent_log_clear_action()
        # Tooltips are transient application UI and must disappear whenever
        # focus leaves the app or the root window is unmapped/minimized.
        self.bind_all("<FocusOut>", self._hide_workflow_tooltips, add="+")
        self.bind("<Unmap>", self._hide_workflow_tooltips, add="+")

    def _install_depot_assessment_action(self) -> None:
        """Add depot assessment beside Resultater without changing the main header."""
        header = self.log_panel.header

        # Keep the established Resultater action in column 1. Move the two
        # existing utility buttons one column right and use column 2 for the
        # new context action.
        self.log_panel.show_button.grid_configure(column=3)
        for child in header.winfo_children():
            if not isinstance(child, ctk.CTkButton):
                continue
            try:
                if str(child.cget("text")) == "Tøm":
                    child.grid_configure(column=4)
                    break
            except Exception:
                continue

        self._depot_assessment_button = ctk.CTkButton(
            header,
            text="Depotvurdering",
            width=104,
            height=22,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._open_depot_assessment,
        )
        self._depot_assessment_button.grid(row=0, column=2, padx=(0, 4))

    def _install_persistent_log_clear_action(self) -> None:
        """Make the visible Tøm action authoritative for the active job log.

        LogPanel.clear() only clears the widget's local display buffer. The
        authoritative per-job history is Job.log_entries and must be cleared
        as well, otherwise switching away and back reconstructs the old log.
        """
        for child in self.log_panel.header.winfo_children():
            if not isinstance(child, ctk.CTkButton):
                continue
            try:
                if str(child.cget("text")) == "Tøm":
                    child.configure(command=self._clear_active_job_log)
                    self._job_log_clear_button = child
                    return
            except Exception:
                continue

    def _clear_active_job_log(self) -> None:
        """Clear both the visible log and the persisted log of the active job."""
        self.log_panel.clear()

        job = self.current_job
        if job is None:
            self.status_bar.set_status("Kjørelogg tømt")
            return

        job.log_entries.clear()

        if self.job_list_path is not None:
            self._write_job_list(self.job_list_path)

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.jobs_window.refresh()
            except Exception:
                pass

        self.status_bar.set_status(f"Kjørelogg tømt for {job.job_id}")

    def _reset_jobs_for_new_job_list_copy(self) -> None:
        """Keep job definitions but remove execution history in a Save As copy.

        Storage roles, workflow, operation parameters, checkpoints, names,
        profiles and stable job identities are retained. Previous execution
        state and the in-job run log belong to the old job list and are not
        carried into the new working copy.

        Persistent result folders, event stores, raw results and PREMIS files
        on disk are deliberately not deleted.
        """
        for job in self.jobs.jobs():
            job.log_entries.clear()
            job.reset_execution("")

    def _save_job_list_as_in(self, directory: Path) -> bool:
        """Save to a new active job list and start it with clean run history.

        The existing job-list file is never rewritten as part of Save As.
        If writing the new target fails, in-memory execution state is restored.
        """
        try:
            filename = filedialog.asksaveasfilename(
                title="Lagre jobbliste som",
                initialdir=str(directory),
                defaultextension=".n5jobs",
                filetypes=[("Workflow-jobbliste", "*.n5jobs"), ("Alle filer", "*.*")],
            )
            if not filename:
                return False

            target = Path(filename)
            old_path = self.job_list_path
            is_new_copy = old_path is not None and target != old_path

            snapshots = []
            if is_new_copy:
                for job in self.jobs.jobs():
                    snapshots.append(
                        (
                            job,
                            list(job.log_entries),
                            job.status,
                            job.progress,
                            job.message,
                            job.next_operation_index,
                        )
                    )
                self._reset_jobs_for_new_job_list_copy()

            self._joblist_explicit_write = True
            try:
                written = self._write_job_list(target)
            finally:
                self._joblist_explicit_write = False

            if not written:
                for job, entries, status, progress, message, next_index in snapshots:
                    job.log_entries = entries
                    job.status = status
                    job.progress = progress
                    job.message = message
                    job.next_operation_index = next_index
                return False

            # _write_job_list() makes target authoritative. Refresh every visible
            # path projection after the asynchronous Save As flow completes.
            self.job_list_path = target
            self._refresh_job_list_status()

            if is_new_copy:
                self.log_panel.clear()
                self.status_bar.set_status(
                    "Ny aktiv jobbliste lagret – tidligere kjøringslogger er nullstilt"
                )
            else:
                self.status_bar.set_status(f"Jobbliste lagret: {target.name}")

            if self.jobs_window is not None:
                try:
                    if self.jobs_window.winfo_exists():
                        self.jobs_window.refresh()
                except Exception:
                    pass

            return True
        finally:
            self._joblist_save_as_active = False

    def _open_depot_assessment(self) -> None:
        self._hide_workflow_tooltips()
        existing = self._depot_assessment_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.focus()
                    existing.lift()
                    return
            except Exception:
                pass

        work_operations = (
            self.current_job.work_operations
            if self.current_job is not None
            else None
        )
        dialog = DepotAssessmentDialog(
            self,
            user_identity=self.current_user_identity(),
            work_operations=work_operations,
        )
        self._depot_assessment_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._depot_assessment_closed(event, d),
            add="+",
        )

    def _depot_assessment_closed(self, event, dialog) -> None:
        if event.widget is dialog and self._depot_assessment_dialog is dialog:
            self._depot_assessment_dialog = None


def run_gui() -> None:
    app = WorkflowApp()
    app.mainloop()
