from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from noark5_workflow.core.job import Job
from noark5_workflow.plugins.noark5.discovery import discover_from_robocopy_logs
from settings import load_config, save_config
from . import theme
from .discovered_sources_dialog import DiscoveredSourcesDialog
from .jobs_window_a15 import A15JobsWindow


class A17JobsWindow(A15JobsWindow):
    """a17 job-list semantics plus a15.1 Noark 5 batch discovery."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._install_discovery_action()

    def _install_discovery_action(self) -> None:
        parent = self.new_button.master
        self.discover_button = ctk.CTkButton(
            parent,
            text="Finn jobber...",
            command=self._discover_jobs,
            width=105,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self.discover_button.pack(side="left", padx=6)

    def set_batch_running(self, running: bool) -> None:
        super().set_batch_running(running)
        if hasattr(self, "discover_button"):
            self.discover_button.configure(state="disabled" if running else "normal")

    def _discover_jobs(self) -> None:
        if self._batch_running:
            return

        settings = load_config()
        kwargs = {
            "title": "Velg Robocopy /L-logg(er) med Noark 5-struktur",
            "filetypes": [
                ("Robocopy/loggfiler", "*.log *.txt"),
                ("Loggfiler", "*.log"),
                ("Tekstfiler", "*.txt"),
                ("Alle filer", "*.*"),
            ],
        }
        previous = str(settings.get("last_noark_discovery_log_dir", "") or "").strip()
        if previous and Path(previous).is_dir():
            kwargs["initialdir"] = previous

        selected_files = filedialog.askopenfilenames(**kwargs)
        if not selected_files:
            return

        paths = [Path(value) for value in selected_files]
        save_config({"last_noark_discovery_log_dir": str(paths[0].parent)})

        try:
            candidates = discover_from_robocopy_logs(paths)
        except Exception as exc:
            messagebox.showerror(
                "Noark 5 Workflow Manager",
                f"Kunne ikke lese Robocopy-loggen(e).\n\n{exc}",
            )
            return

        if not candidates:
            messagebox.showinfo(
                "Noark 5 Workflow Manager",
                "Ingen mulige Noark 5-uttrekk ble funnet.\n\n"
                "a15.1 ser etter mapper som inneholder arkivstruktur.xml og "
                "utelukker kjente schema-, rapport-, test- og arbeidsområder.",
            )
            return

        existing_sources = {
            str(job.active_extraction_root)
            for job in self.batch.jobs()
            if job.active_extraction_root is not None
        }
        dialog = DiscoveredSourcesDialog(
            self, candidates, existing_sources=existing_sources
        )
        self.wait_window(dialog)

        chosen = dialog.selected
        if not chosen:
            return

        created: list[Job] = []
        jobs = self.batch.jobs()
        reusable_draft = (
            jobs[0] if len(jobs) == 1 and jobs[0].is_unused_draft() else None
        )

        for index, candidate in enumerate(chosen):
            if index == 0 and reusable_draft is not None:
                job = reusable_draft
                job.source_root = Path(candidate.path)
                job.source_extraction = None
                job.name = candidate.suggested_name
            else:
                job = self.on_create_job(Path(candidate.path))
                job.name = candidate.suggested_name

            job.profile_id = "noark5"
            created.append(job)

        self._persist_list_change()
        self.refresh()

        messagebox.showinfo(
            "Noark 5 Workflow Manager",
            f"{len(created)} jobb(er) ble lagt til jobblisten.\n\n"
            "Source er satt til den oppdagede Noark 5-roten. "
            "Work/Storage settes i neste steg.",
        )

    def _delete(self, job) -> None:
        if self._batch_running:
            return

        jobs = self.batch.jobs()
        if len(jobs) == 1:
            messagebox.showinfo(
                "Data Workflow Manager",
                "Dette er siste jobb i jobblista.\n\n"
                "Bruk «Ny jobbliste» for å starte helt på nytt. "
                "Da tømmes den aktive jobblista og visningsloggen, "
                "og første nye jobb får JOB-001.\n\n"
                "Persistente kjørelogger, råresultater og PREMIS-filer på disk slettes ikke.",
            )
            return

        super()._delete(job)
