from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from app.storage_layouts import materialize_storage_roles, storage_layout_by_id
from app.workflow_sequences import workflow_sequence_by_id
from noark5_workflow.core.job import JobStatus
from settings import save_config
from version import APP_NAME
from . import theme
from .persistent_app_a23 import WorkflowApp as A23WorkflowApp


class WorkflowApp(A23WorkflowApp):
    """a15.6.1: restore maximized state and expose Standard on active job."""

    def __init__(self) -> None:
        super().__init__()
        self._install_active_job_standard_button()
        self.after_idle(self._restore_maximized_state)
        self.after(150, self._restore_maximized_state)

    def _restore_maximized_state(self) -> None:
        if not bool(self.settings.get("restore_main_window_maximized", True)):
            return
        if not bool(self.settings.get("main_window_maximized", False)):
            return
        try:
            self.state("zoomed")
        except Exception:
            return

    def _capture_maximized_state(self) -> None:
        try:
            maximized = str(self.state()).lower() == "zoomed"
        except Exception:
            maximized = False
        self.settings["main_window_maximized"] = maximized
        try:
            save_config({"main_window_maximized": maximized})
        except Exception:
            pass

    def _close_with_persistence(self) -> None:
        self._capture_maximized_state()
        super()._close_with_persistence()

    def _install_active_job_standard_button(self) -> None:
        actions = getattr(self, "_a17_header_actions", None)
        if actions is None:
            return
        before_widget = None
        for child in actions.winfo_children():
            if isinstance(child, ctk.CTkButton):
                try:
                    if str(child.cget("text")) == "Jobber":
                        before_widget = child
                        break
                except Exception:
                    pass
        self.standard_job_button = ctk.CTkButton(
            actions,
            text="Standard",
            width=76,
            height=28,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._apply_standard_to_current_job,
        )
        kwargs = dict(side="left", padx=2, pady=8)
        if before_widget is not None:
            kwargs["before"] = before_widget
        self.standard_job_button.pack(**kwargs)

    def _apply_standard_to_current_job(self) -> None:
        if self.batch_running:
            messagebox.showwarning(
                APP_NAME,
                "Standardoppsett kan ikke endres mens Start alle kjører.",
            )
            return

        job = self.current_job
        if job is None:
            messagebox.showwarning(APP_NAME, "Åpne en jobb først.")
            return

        extraction = job.source_extraction or job.active_extraction_root
        if extraction is None:
            messagebox.showwarning(
                APP_NAME,
                f"{job.job_id}\n\nSource extraction er ikke satt. Velg Source først.",
            )
            return

        layout_id = str(
            self.settings.get("storage_layout_profile", "ikamr_standard") or "none"
        )
        workflow_id = str(
            self.settings.get("noark5_discovery_workflow", "noark5_standard") or "none"
        )
        layout = storage_layout_by_id(layout_id)
        sequence = workflow_sequence_by_id(workflow_id)
        roles = materialize_storage_roles(Path(extraction), layout_id=layout_id)

        old_workflow = list(job.workflow_ids)
        new_workflow = list(sequence.operation_ids) if sequence is not None else old_workflow
        role_changes = [
            (attr, getattr(job, attr, None), new_value)
            for attr, new_value in roles.items()
            if getattr(job, attr, None) != new_value
        ]
        workflow_changes = sequence is not None and old_workflow != new_workflow
        profile_change = job.profile_id != "noark5"

        if not role_changes and not workflow_changes and not profile_change:
            messagebox.showinfo(
                APP_NAME,
                f"{job.job_id}\n\nJobben bruker allerede valgt standardoppsett.",
            )
            return

        lines = [
            f"{job.job_id} - {job.name}",
            "",
            f"Mappeprofil: {layout.label}",
            f"Workflow: {sequence.name}" if sequence is not None else "Workflow: behold eksisterende",
        ]
        if role_changes:
            lines.append(f"Mappe-roller som endres: {len(role_changes)}")
        if workflow_changes:
            lines.append(
                f"Workflow endres: {len(old_workflow)} -> {len(new_workflow)} operasjoner"
            )
        lines += [
            "",
            "Eksisterende verdier som avviker fra valgt standard blir erstattet.",
            "Tidligere resultatfiler på disk slettes ikke.",
            "",
            "Bruke standardoppsettet?",
        ]
        if not messagebox.askyesno(APP_NAME, "\n".join(lines)):
            return

        for attr, value in roles.items():
            setattr(job, attr, Path(value))

        job.profile_id = "noark5"
        if sequence is not None:
            job.set_workflow(sequence.operation_ids)

        if (
            (workflow_changes or role_changes)
            and job.status in {
                JobStatus.OK, JobStatus.FAILED, JobStatus.SKIPPED, JobStatus.WAITING
            }
        ):
            job.reset_execution("Standardoppsett endret - klar for ny kjøring")

        self._apply_profile("noark5", persist=False)
        self.workflow.clear()
        for operation_id in job.workflow_ids:
            self.workflow.add(operation_id)
        self.workflow_panel.refresh()

        active_source = job.active_extraction_root
        self.source_panel.path_var.set(
            str(active_source) if active_source is not None else ""
        )
        self.source_panel.detect()
        self._refresh_active_job_label()
        self._update_run_button()

        if self.job_list_path is not None:
            self._write_job_list(self.job_list_path)

        jobs_window = getattr(self, "jobs_window", None)
        if jobs_window is not None:
            try:
                if jobs_window.winfo_exists():
                    jobs_window.refresh()
            except Exception:
                pass

        self.status_bar.set_status(f"Standardoppsett brukt på {job.job_id}")


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
