
from __future__ import annotations

from tkinter import messagebox, simpledialog

import customtkinter as ctk

from app.workflow_sequences import (
    WorkflowSequence,
    delete_custom_workflow_sequence,
    load_workflow_sequences,
    save_custom_workflow_sequence,
)
from noark5_workflow.core.job import JobStatus
from version import APP_NAME

from . import theme
from .persistent_app_a54 import WorkflowApp as A54WorkflowApp
from .workflow_profiles_dialog import WorkflowProfilesDialog


_TERMINAL = {
    JobStatus.OK,
    JobStatus.FAILED,
    JobStatus.SKIPPED,
    JobStatus.WAITING,
}


class WorkflowApp(A54WorkflowApp):
    """v0.1.5-a20: reusable built-in and user-defined workflow profiles."""

    def __init__(self) -> None:
        super().__init__()
        self._install_workflow_profile_controls()

    def _install_workflow_profile_controls(self) -> None:
        panel = self.workflow_panel

        panel.save_profile_button.configure(
            text="Lagre profil...",
            command=self._save_current_workflow_profile,
            state="normal",
        )

        parent = panel.save_profile_button.master
        self.choose_workflow_profile_button = ctk.CTkButton(
            parent,
            text="Velg profil...",
            command=self._open_workflow_profiles,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            height=28,
            font=theme.font(theme.SMALL_SIZE),
        )
        self.choose_workflow_profile_button.grid(
            row=1,
            column=0,
            columnspan=2,
            padx=0,
            pady=(6, 0),
            sticky="ew",
        )

    def _current_profile_id(self) -> str:
        job = self.current_job
        profile_id = str(getattr(job, "profile_id", "") or "") if job else ""
        return profile_id or "noark5"

    def _save_current_workflow_profile(self) -> None:
        if self.batch_running:
            return

        operation_ids = tuple(self.workflow.operation_ids())
        if not operation_ids:
            messagebox.showwarning(
                APP_NAME,
                "Workflowen må inneholde minst én operasjon før den kan lagres som profil.",
            )
            return

        name = simpledialog.askstring(
            "Lagre workflowprofil",
            "Navn på brukerprofil:",
            parent=self,
        )
        if not name:
            return

        try:
            sequence = save_custom_workflow_sequence(
                name=name,
                profile_id=self._current_profile_id(),
                operation_ids=operation_ids,
                description="Brukerdefinert workflow lagret fra hovedvinduet.",
            )
        except ValueError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return

        self.settings["custom_workflow_sequences"] = [
            {
                "sequence_id": item.sequence_id,
                "name": item.name,
                "profile_id": item.profile_id,
                "description": item.description,
                "operation_ids": list(item.operation_ids),
            }
            for item in load_workflow_sequences()
            if item.is_custom
        ]
        self.status_bar.set_status(f"Workflowprofil lagret: {sequence.name}")

    def _open_workflow_profiles(self) -> None:
        if self.batch_running:
            return

        sequences = [
            sequence
            for sequence in load_workflow_sequences()
            if sequence.profile_id in {"", self._current_profile_id()}
        ]

        WorkflowProfilesDialog(
            self,
            sequences,
            on_apply=self._apply_workflow_profile,
            on_delete=self._delete_workflow_profile,
        )

    def _apply_workflow_profile(self, sequence: WorkflowSequence) -> bool:
        job = self.current_job

        if job is not None and tuple(job.workflow_ids) != tuple(sequence.operation_ids):
            if job.status in _TERMINAL:
                confirmed = messagebox.askyesno(
                    APP_NAME,
                    "Jobben har allerede kjørestatus/resultater.\n\n"
                    f"Erstatte workflow med «{sequence.name}» og nullstille "
                    "kjørestatus/cursor?\n\n"
                    "Eksisterende resultatfiler på disk slettes ikke.",
                )
                if not confirmed:
                    return False
                job.reset_execution("Workflowprofil endret - klar for ny kjøring")

        self.workflow.clear()
        for operation_id in sequence.operation_ids:
            self.workflow.add(operation_id)
        self.workflow_panel.refresh()

        if job is not None:
            job.profile_id = sequence.profile_id or job.profile_id
            job.set_workflow(sequence.operation_ids)
            if self.job_list_path is not None:
                self._write_job_list(self.job_list_path)

        self._refresh_active_job_label()
        self.status_bar.set_status(f"Workflowprofil valgt: {sequence.name}")
        return True

    def _delete_workflow_profile(self, sequence: WorkflowSequence) -> bool:
        if not sequence.is_custom:
            return False

        if not messagebox.askyesno(
            APP_NAME,
            f"Slette brukerprofilen «{sequence.name}»?\n\n"
            "Jobber som allerede har denne workflowen endres ikke.",
        ):
            return False

        if not delete_custom_workflow_sequence(sequence.sequence_id):
            messagebox.showerror(APP_NAME, "Kunne ikke slette brukerprofilen.")
            return False

        self.status_bar.set_status(f"Workflowprofil slettet: {sequence.name}")
        return True


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
