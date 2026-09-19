from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.storage_layouts import materialize_storage_roles, storage_layout_by_id, suggested_job_name
from app.workflow_sequences import workflow_sequence_by_id
from noark5_workflow.core.job import Job, JobStatus
from noark5_workflow.plugins.noark5.discovery import discover_from_robocopy_logs
from settings import load_config, save_config
from . import theme
from .discovered_sources_dialog import DiscoveredSourcesDialog
from .jobs_window import _CHANGED_AFTER_RUN
from .jobs_window_a15 import A15JobsWindow


class A17JobsWindow(A15JobsWindow):
    """Job overview plus Noark 5 discovery and efficient batch status updates."""

    def __init__(self, *args, **kwargs) -> None:
        self._row_views: dict[str, dict] = {}
        self._rendered_job_ids: tuple[str, ...] = ()
        super().__init__(*args, **kwargs)
        self._install_discovery_action()
        self._install_start_ready_action()

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

    def _install_start_ready_action(self) -> None:
        parent = self.start_all_button.master
        self.start_ready_button = ctk.CTkButton(
            parent,
            text="Start klare",
            command=self._start_ready_jobs,
            width=100,
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
        )
        self.start_ready_button.pack(
            side="left",
            padx=6,
            before=self.stop_button,
        )
        self._update_start_ready_state()

    def _start_ready_jobs(self) -> None:
        if self._batch_running:
            return
        callback = getattr(self.master, "_start_ready_jobs", None)
        if not callable(callback):
            messagebox.showwarning(
                "Noark 5 Workflow Manager",
                "Kjøring av klare jobber er ikke tilgjengelig i denne runtime-versjonen.",
            )
            return
        callback()

    @staticmethod
    def _is_ready_to_run(job: Job) -> bool:
        if not job.workflow_ids:
            return False
        return job.status in {JobStatus.READY, JobStatus.WAITING}

    def _ready_count(self) -> int:
        return sum(1 for job in self.batch.jobs() if self._is_ready_to_run(job))

    def _update_start_ready_state(self) -> None:
        if not hasattr(self, "start_ready_button"):
            return
        disabled = self._batch_running or self._ready_count() == 0
        self.start_ready_button.configure(
            state="disabled" if disabled else "normal"
        )

    def set_batch_running(self, running: bool) -> None:
        super().set_batch_running(running)
        if hasattr(self, "discover_button"):
            self.discover_button.configure(state="disabled" if running else "normal")
        self._update_row_action_states()
        self._update_start_ready_state()

    # ------------------------------------------------------------------
    # Stable/in-place Jobber refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        jobs = self.batch.jobs()
        job_ids = tuple(job.job_id for job in jobs)

        if (
            job_ids == self._rendered_job_ids
            and len(self._row_views) == len(jobs)
            and all(job_id in self._row_views for job_id in job_ids)
        ):
            path = self.get_list_path()
            self.file_label.configure(
                text=f"Jobbliste: {path if path else '(ikke lagret)'}"
            )
            active_job_id = self.get_active_job_id()
            for row, job in enumerate(jobs):
                self._update_row_view(
                    row,
                    job,
                    active=(job.job_id == active_job_id),
                    can_move_up=(row > 0),
                    can_move_down=(row < len(jobs) - 1),
                )
            self._update_summary(jobs)
            self.set_batch_running(self._batch_running)
            return

        self._row_views.clear()
        super().refresh()
        self._rendered_job_ids = job_ids
        self._update_summary(jobs)
        self._update_start_ready_state()

    def _update_summary(self, jobs: list[Job]) -> None:
        counts = self.batch.counts()
        waiting = counts.get(JobStatus.WAITING, 0)
        ready_to_run = self._ready_count()
        self.summary.configure(
            text=(
                f"Totalt: {len(jobs)}   |   Ferdig: {counts[JobStatus.OK]}   |   "
                f"Kjører: {counts[JobStatus.RUNNING]}   |   Venter: {waiting}   |   "
                f"Klar: {counts[JobStatus.READY]}   |   Feil: {counts[JobStatus.FAILED]}   |   "
                f"Hoppet over: {counts[JobStatus.SKIPPED]}   |   "
                f"Kjørbare nå: {ready_to_run}"
            )
        )

    def _status_text(self, job: Job) -> str:
        if job.status == JobStatus.READY and job.message == _CHANGED_AFTER_RUN:
            return "Klar – endret etter kjøring"
        return job.status.value

    def _status_color(self, job: Job):
        if job.status == JobStatus.RUNNING:
            return theme.BLUE
        if job.status == JobStatus.FAILED:
            return theme.DANGER_TEXT
        return theme.TEXT_SUB

    def _row(
        self,
        row: int,
        job: Job,
        *,
        active: bool = False,
        can_move_up: bool = True,
        can_move_down: bool = True,
    ) -> None:
        card = ctk.CTkFrame(
            self.list_frame,
            fg_color=theme.BLUE_DIM if active else theme.CARD_BG,
            corner_radius=6,
        )
        card.grid(row=row, column=0, padx=5, pady=4, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, padx=8, pady=(7, 0), sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        id_label = ctk.CTkLabel(
            top, text="", width=130, anchor="w",
            font=theme.font(theme.SMALL_SIZE, "bold"),
        )
        id_label.grid(row=0, column=0, padx=(0, 8), sticky="w")

        name_label = ctk.CTkLabel(
            top, text="", anchor="w",
            font=theme.font(theme.SMALL_SIZE, "bold"),
        )
        name_label.grid(row=0, column=1, sticky="ew")

        status_label = ctk.CTkLabel(
            top, text="", width=185, anchor="w",
            font=theme.font(theme.SMALL_SIZE),
        )
        status_label.grid(row=0, column=2, padx=8, sticky="w")

        progress_label = ctk.CTkLabel(
            top, text="", width=55, font=theme.font(theme.SMALL_SIZE),
        )
        progress_label.grid(row=0, column=3, padx=8)

        worker_label = ctk.CTkLabel(
            top, text="", width=145, anchor="w",
            font=theme.font(theme.SMALL_SIZE),
        )
        worker_label.grid(row=0, column=4, padx=8, sticky="w")

        up_button = ctk.CTkButton(
            top, text="↑", width=32, height=27,
            command=lambda j=job: self._move_up(j),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        up_button.grid(row=0, column=5, padx=(6, 2))

        down_button = ctk.CTkButton(
            top, text="↓", width=32, height=27,
            command=lambda j=job: self._move_down(j),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        down_button.grid(row=0, column=6, padx=2)

        delete_button = ctk.CTkButton(
            top, text="Slett", width=58, height=27,
            command=lambda j=job: self._delete(j),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        delete_button.grid(row=0, column=7, padx=2)

        mapper_button = ctk.CTkButton(
            top, text="Mapper", width=66, height=27,
            command=lambda j=job: self._edit_job_mappers(j),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        mapper_button.grid(row=0, column=8, padx=2)

        standard_button = ctk.CTkButton(
            top, text="Standard", width=76, height=27,
            command=lambda j=job: self._apply_standard_setup(j),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        standard_button.grid(row=0, column=9, padx=2)

        open_button = ctk.CTkButton(
            top, text="Åpne", width=70, height=27,
            command=lambda j=job: self._open(j),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        open_button.grid(row=0, column=10, padx=(2, 0))

        details = ctk.CTkFrame(card, fg_color="transparent")
        details.grid(row=1, column=0, columnspan=2, padx=8, pady=(2, 7), sticky="ew")
        details.grid_columnconfigure(1, weight=1)

        source_label = ctk.CTkLabel(
            details, text="", anchor="w",
            font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MUTED,
        )
        source_label.grid(row=0, column=0, padx=(0, 18), sticky="w")

        output_label = ctk.CTkLabel(
            details, text="", anchor="w",
            font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MUTED,
        )
        output_label.grid(row=0, column=1, sticky="ew")

        message_label = ctk.CTkLabel(
            details, text="", anchor="w",
            font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_SUB,
        )
        message_label.grid(row=1, column=0, columnspan=2, pady=(2, 0), sticky="ew")

        self._row_views[job.job_id] = {
            "card": card, "id": id_label, "name": name_label,
            "status": status_label, "progress": progress_label,
            "worker": worker_label, "up": up_button, "down": down_button,
            "delete": delete_button, "mapper": mapper_button,
            "standard": standard_button, "open": open_button,
            "source": source_label, "output": output_label,
            "message": message_label,
        }
        self._update_row_view(
            row, job, active=active,
            can_move_up=can_move_up, can_move_down=can_move_down,
        )

    def _update_row_view(
        self, row: int, job: Job, *,
        active: bool, can_move_up: bool, can_move_down: bool,
    ) -> None:
        view = self._row_views.get(job.job_id)
        if view is None:
            return
        view["card"].configure(fg_color=theme.BLUE_DIM if active else theme.CARD_BG)
        view["id"].configure(
            text=f"{job.job_id}  • AKTIV" if active else job.job_id,
            text_color=theme.BLUE if active else theme.TEXT_SUB,
        )
        view["name"].configure(
            text=job.name, text_color=theme.BLUE if active else theme.TEXT_SUB,
        )
        view["status"].configure(
            text=self._status_text(job), text_color=self._status_color(job),
        )
        view["progress"].configure(text=f"{job.progress:.0%}")
        view["worker"].configure(text=job.worker)
        view["source"].configure(text=f"Kilde: {job.source_root}")
        view["output"].configure(text=f"Utdata: {job.output_root or '(ikke valgt)'}")
        view["message"].configure(text=job.message or "")

        state = "disabled" if self._batch_running else "normal"
        view["up"].configure(state=state if can_move_up else "disabled")
        view["down"].configure(state=state if can_move_down else "disabled")
        for key in ("delete", "mapper", "standard", "open"):
            view[key].configure(state=state)

    def _update_row_action_states(self) -> None:
        jobs = self.batch.jobs()
        if not self._row_views:
            return
        for row, job in enumerate(jobs):
            self._update_row_view(
                row, job,
                active=(job.job_id == self.get_active_job_id()),
                can_move_up=(row > 0),
                can_move_down=(row < len(jobs) - 1),
            )

    def _edit_job_mappers(self, job: Job) -> None:
        if self._batch_running:
            return
        callback = getattr(self.master, "_show_storage_roles", None)
        if not callable(callback):
            messagebox.showwarning(
                "Noark 5 Workflow Manager",
                "Mapper-dialogen er ikke tilgjengelig i denne runtime-versjonen.",
            )
            return
        callback(job)

    @staticmethod
    def _apply_roles(job: Job, roles: dict[str, Path]) -> None:
        for attr in (
            "source_root", "source_tar", "source_unzipped", "source_extraction",
            "work_root", "work_content", "work_operations", "archive_root",
        ):
            if attr in roles:
                setattr(job, attr, Path(roles[attr]))

    def _apply_standard_setup(self, job: Job) -> None:
        if self._batch_running:
            return

        settings = load_config()
        layout_id = str(settings.get("storage_layout_profile", "ikamr_standard") or "none")
        workflow_id = str(settings.get("noark5_discovery_workflow", "noark5_standard") or "none")
        layout = storage_layout_by_id(layout_id)
        sequence = workflow_sequence_by_id(workflow_id)

        extraction = job.source_extraction or job.active_extraction_root
        if extraction is None:
            messagebox.showwarning(
                "Noark 5 Workflow Manager",
                f"{job.job_id}\n\nSource extraction er ikke satt. Velg Source først.",
            )
            return

        roles = materialize_storage_roles(Path(extraction), layout_id=layout_id)
        old_workflow = list(job.workflow_ids)
        new_workflow = list(sequence.operation_ids) if sequence is not None else old_workflow

        role_changes = []
        for attr, new_value in roles.items():
            old_value = getattr(job, attr, None)
            if old_value != new_value:
                role_changes.append((attr, old_value, new_value))

        workflow_changes = sequence is not None and old_workflow != new_workflow
        profile_change = job.profile_id != "noark5"

        if not role_changes and not workflow_changes and not profile_change:
            messagebox.showinfo(
                "Noark 5 Workflow Manager",
                f"{job.job_id}\n\nJobben bruker allerede valgt standardoppsett.",
            )
            return

        lines = [
            f"{job.job_id} – {job.name}", "",
            f"Mappeprofil: {layout.label}",
            f"Workflow: {sequence.name}" if sequence is not None else "Workflow: behold eksisterende",
        ]
        if role_changes:
            lines.append(f"Mappe-roller som endres: {len(role_changes)}")
        if workflow_changes:
            lines.append(f"Workflow endres: {len(old_workflow)} → {len(new_workflow)} operasjoner")
        lines.extend([
            "",
            "Eksisterende verdier som avviker fra valgt standard blir erstattet.",
            "Tidligere resultatfiler på disk slettes ikke.",
            "",
            "Bruke standardoppsettet?",
        ])

        if not messagebox.askyesno("Noark 5 Workflow Manager", "\n".join(lines)):
            return

        self._apply_roles(job, roles)
        job.profile_id = "noark5"
        if sequence is not None:
            job.set_workflow(sequence.operation_ids)

        if (
            (workflow_changes or role_changes)
            and job.status in {
                JobStatus.OK, JobStatus.FAILED, JobStatus.SKIPPED, JobStatus.WAITING,
            }
        ):
            job.reset_execution("Standardoppsett endret - klar for ny kjøring")

        self._persist_list_change()
        self.refresh()

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
                "Ingen mulige Noark 5-uttrekk ble funnet.",
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

        layout_id = str(settings.get("storage_layout_profile", "ikamr_standard") or "none")
        workflow_sequence_id = str(
            settings.get("noark5_discovery_workflow", "noark5_standard") or "none"
        )
        workflow_sequence = workflow_sequence_by_id(workflow_sequence_id)

        created: list[Job] = []
        jobs = self.batch.jobs()

        if jobs and all(job.is_unused_draft() for job in jobs):
            reusable_draft = jobs[0]
            for extra in jobs[1:]:
                self.batch.remove(extra.job_id)
            jobs = self.batch.jobs()
        else:
            reusable_draft = (
                jobs[0] if len(jobs) == 1 and jobs[0].is_unused_draft() else None
            )

        owner_identity = next(
            (job.owner_identity for job in jobs if job.owner_identity), None
        )

        for index, candidate in enumerate(chosen):
            extraction_root = Path(candidate.path)
            roles = materialize_storage_roles(extraction_root, layout_id=layout_id)
            name = suggested_job_name(extraction_root, layout_id=layout_id)

            if index == 0 and reusable_draft is not None:
                job = reusable_draft
                self._apply_roles(job, roles)
                job.name = name
            else:
                job = self.batch.new_job(
                    roles.get("source_root") or extraction_root,
                    name=name,
                )
                self._apply_roles(job, roles)
                job.set_owner_identity(owner_identity)

            job.profile_id = "noark5"
            if workflow_sequence is not None:
                job.set_workflow(workflow_sequence.operation_ids)
            created.append(job)

        self._persist_list_change()
        self.refresh()

        workflow_text = (
            f"Workflow: {workflow_sequence.name} "
            f"({len(workflow_sequence.operation_ids)} operasjoner)."
            if workflow_sequence is not None
            else "Workflow: ingen automatisk tildeling."
        )
        messagebox.showinfo(
            "Noark 5 Workflow Manager",
            f"{len(created)} jobb(er) ble lagt til jobblisten.\n\n"
            + (
                "Source/Work/Storage er automatisk fylt fra valgt mappeoppsett.\n"
                if layout_id != "none"
                else "Source extraction er satt. Andre mapper fylles ikke automatisk.\n"
            )
            + workflow_text,
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
