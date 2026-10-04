from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from noark5_workflow.core.job import Job, JobBatch, JobStatus
from settings import load_config, save_config
from . import theme


_CHANGED_AFTER_RUN = "Konfigurasjon endret - klar for ny kjøring"


class JobsWindow(ctk.CTkToplevel):
    """Top-level job/batch overview."""

    def __init__(
        self,
        master,
        batch: JobBatch,
        on_open_job: Callable[[Job], None],
        on_create_job: Callable[[Path], Job],
        on_start_all: Callable[[], None],
        on_start_selected: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
        on_new_list: Callable[[], bool] | None = None,
        on_open_list: Callable[[], bool] | None = None,
        on_save_list: Callable[[], bool] | None = None,
        on_save_list_as: Callable[[], bool] | None = None,
        get_list_path: Callable[[], Path | None] | None = None,
        get_active_job_id: Callable[[], str | None] | None = None,
    ) -> None:
        super().__init__(master)
        self.batch = batch
        self.on_open_job = on_open_job
        self.on_create_job = on_create_job
        self.on_start_all = on_start_all
        self.on_start_selected = on_start_selected or on_start_all
        self.on_stop = on_stop or (lambda: None)
        self.on_new_list = on_new_list or (lambda: False)
        self.on_open_list = on_open_list or (lambda: False)
        self.on_save_list = on_save_list or (lambda: False)
        self.on_save_list_as = on_save_list_as or (lambda: False)
        self.get_list_path = get_list_path or (lambda: None)
        self.get_active_job_id = get_active_job_id or (lambda: None)
        self.settings = load_config()
        self._batch_running = False
        self._refresh_scheduled = False
        self._selected_job_ids: set[str] = {job.job_id for job in self.batch.jobs()}
        self.title("Jobber - Noark 5 Workflow Manager")
        self.geometry("1480x780")
        self.minsize(1120, 640)
        self.configure(fg_color=theme.APP_BG)
        self.resizable(True, True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self, fg_color=theme.APP_BG, corner_radius=0)
        header.grid(row=0, column=0, padx=18, pady=(14, 4), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="JOBBER", font=theme.font(theme.TITLE_SIZE, "bold"), text_color=theme.BLUE
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Persistent jobbliste. Start alle kjører jobbene sekvensielt på lokal worker.",
            font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MUTED,
        ).grid(row=1, column=0, pady=(4, 0), sticky="w")

        self.file_label = ctk.CTkLabel(
            self,
            text="Jobbliste: (ikke lagret)",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_SUB,
            anchor="w",
        )
        self.file_label.grid(row=1, column=0, padx=18, pady=(0, 4), sticky="ew")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=2, column=0, padx=18, pady=8, sticky="ew")

        self.new_list_button = ctk.CTkButton(
            buttons, text="Ny jobbliste", command=self._new_list, width=105,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        self.new_list_button.pack(side="left", padx=(0, 4))
        self.open_list_button = ctk.CTkButton(
            buttons, text="Åpne...", command=self._open_list, width=82,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        self.open_list_button.pack(side="left", padx=4)
        self.save_list_button = ctk.CTkButton(
            buttons, text="Lagre", command=self._save_list, width=75,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        self.save_list_button.pack(side="left", padx=4)
        self.save_as_button = ctk.CTkButton(
            buttons, text="Lagre som...", command=self._save_list_as, width=100,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        self.save_as_button.pack(side="left", padx=(4, 14))

        self.new_button = ctk.CTkButton(
            buttons, text="+ Ny jobb", command=self._new_job, width=100,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER
        )
        self.new_button.pack(side="left", padx=(0, 6))
        self.start_all_button = ctk.CTkButton(
            buttons, text="Start alle", command=self.on_start_all, width=100,
            fg_color=theme.BLUE_DIM, hover_color=theme.BLUE,
        )
        self.start_all_button.pack(side="left", padx=6)
        self.start_selected_button = ctk.CTkButton(
            buttons, text="Start valgte", command=self.on_start_selected, width=110,
            fg_color=theme.BLUE_DIM, hover_color=theme.BLUE,
        )
        self.start_selected_button.pack(side="left", padx=6)
        self.stop_button = ctk.CTkButton(
            buttons, text="Stopp", command=self.on_stop, width=80, state="disabled",
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        self.stop_button.pack(side="left", padx=6)
        self.scheduler_label = ctk.CTkLabel(
            buttons,
            text="Scheduler: lokal / sekvensiell   |   Worker: Lokal (denne PC-en)",
            font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MUTED,
        )
        self.scheduler_label.pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=theme.PANEL_BG_DARK, corner_radius=8)
        self.list_frame.grid(row=3, column=0, padx=18, pady=(0, 8), sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)

        self.summary = ctk.CTkLabel(
            self, text="", font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_SUB
        )
        self.summary.grid(row=4, column=0, padx=18, pady=(2, 14), sticky="w")
        self.refresh()

    def set_batch_running(self, running: bool) -> None:
        self._batch_running = bool(running)
        state = "disabled" if running else "normal"
        self.new_list_button.configure(state=state)
        self.open_list_button.configure(state=state)
        self.save_list_button.configure(state=state)
        self.save_as_button.configure(state=state)
        self.new_button.configure(state=state)
        self.start_all_button.configure(state="disabled" if running or len(self.batch) == 0 else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.scheduler_label.configure(
            text=("Scheduler: KJØRER sekvensielt   |   Worker: Lokal (denne PC-en)"
                  if running else "Scheduler: lokal / sekvensiell   |   Worker: Lokal (denne PC-en)"),
            text_color=theme.BLUE if running else theme.TEXT_MUTED,
        )
        self.start_selected_button.configure(state="disabled" if running or not self._selected_job_ids else "normal")

    def _selected_job_ids_for_run(self) -> set[str]:
        selected = self._selected_job_ids if isinstance(self._selected_job_ids, set) else set()
        return set(selected)

    def _selected_jobs_for_run(self) -> tuple[Job, ...]:
        selected = self._selected_job_ids_for_run()
        return tuple(job for job in self.batch.jobs() if job.job_id in selected)

    def _select_all(self) -> None:
        self._selected_job_ids = {job.job_id for job in self.batch.jobs()}
        if self.winfo_exists():
            self.refresh()

    def _clear_selection(self) -> None:
        self._selected_job_ids = set()
        if self.winfo_exists():
            self.refresh()

    def _new_list(self) -> None:
        if not self._batch_running and self.on_new_list():
            self.refresh()

    def _open_list(self) -> None:
        if not self._batch_running and self.on_open_list():
            self.refresh()

    def _save_list(self) -> None:
        if not self._batch_running and self.on_save_list():
            self.refresh()

    def _save_list_as(self) -> None:
        if not self._batch_running and self.on_save_list_as():
            self.refresh()

    def _persist_list_change(self) -> None:
        if self.get_list_path() is not None:
            self.on_save_list()

    def _toggle_selection(self, job_id: str) -> None:
        if job_id in self._selected_job_ids:
            self._selected_job_ids.remove(job_id)
        else:
            self._selected_job_ids.add(job_id)
        self.refresh()

    def _move_up(self, job: Job) -> None:
        if self._batch_running:
            return
        if self.batch.move_up(job.job_id):
            self._persist_list_change()
            self.refresh()

    def _move_down(self, job: Job) -> None:
        if self._batch_running:
            return
        if self.batch.move_down(job.job_id):
            self._persist_list_change()
            self.refresh()

    def _delete(self, job: Job) -> None:
        if self._batch_running:
            return

        jobs = self.batch.jobs()
        if len(jobs) == 1 and self.get_active_job_id() == job.job_id:
            messagebox.showinfo(
                "Noark 5 Workflow Manager",
                "Dette er siste aktive jobb i jobblista.\n\n"
                "Bruk «Ny jobbliste» dersom du vil tømme hele jobblista.",
            )
            return

        if not messagebox.askyesno(
            "Noark 5 Workflow Manager",
            f"Slette {job.job_id} fra jobblista?\n\n"
            "Kilde, utdata og tidligere resultatmapper på disk slettes ikke.",
        ):
            return

        active = self.get_active_job_id() == job.job_id
        replacement = None
        if active:
            index = next((i for i, item in enumerate(jobs) if item.job_id == job.job_id), 0)
            remaining = [item for item in jobs if item.job_id != job.job_id]
            if remaining:
                replacement = remaining[min(index, len(remaining) - 1)]

        if not self.batch.remove(job.job_id):
            return

        if replacement is not None:
            self.on_open_job(replacement)

        self._persist_list_change()
        self.refresh()

    def _new_job(self) -> None:
        kwargs = {"title": "Velg rotmappe for ny Noark 5-jobb"}
        previous = str(self.settings.get("last_noark_source_dir", "")).strip()
        if previous and Path(previous).is_dir():
            kwargs["initialdir"] = previous
        folder = filedialog.askdirectory(**kwargs)
        if not folder:
            return
        save_config({"last_noark_source_dir": folder})
        job = self.on_create_job(Path(folder))
        self.refresh()
        self._open(job)

    def _open(self, job: Job) -> None:
        self.on_open_job(job)
        if not self._batch_running:
            self.destroy()

    def schedule_refresh(self) -> None:
        if not self.winfo_exists():
            return
        if self._refresh_scheduled:
            return
        self._refresh_scheduled = True
        self.after(80, self._flush_refresh)

    def _flush_refresh(self) -> None:
        self._refresh_scheduled = False
        if self.winfo_exists():
            self.refresh()

    def refresh(self) -> None:
        path = self.get_list_path()
        self.file_label.configure(text=f"Jobbliste: {path if path else '(ikke lagret)'}")

        for child in self.list_frame.winfo_children():
            child.destroy()

        jobs = self.batch.jobs()
        active_job_id = self.get_active_job_id()

        if not jobs:
            ctk.CTkLabel(
                self.list_frame,
                text="Ingen jobber ennå.\nVelg «+ Ny jobb» for å opprette første jobb.",
                font=theme.font(theme.NORMAL_SIZE), text_color=theme.TEXT_MUTED, justify="center",
            ).grid(row=0, column=0, padx=20, pady=80)
        else:
            selection_bar = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            selection_bar.grid(row=0, column=0, padx=5, pady=(4, 6), sticky="ew")
            selection_bar.grid_columnconfigure(1, weight=1)
            ctk.CTkButton(
                selection_bar, text="Velg alle", width=110,
                command=self._select_all,
                fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
            ).grid(row=0, column=0, padx=(0, 6), sticky="w")
            ctk.CTkButton(
                selection_bar, text="Tøm valg", width=110,
                command=self._clear_selection,
                fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
            ).grid(row=0, column=1, padx=(0, 6), sticky="w")
            ctk.CTkLabel(
                selection_bar,
                text=f"Valgt: {len(self._selected_job_ids_for_run())} av {len(jobs)}",
                font=theme.font(theme.SMALL_SIZE, "bold"),
                text_color=theme.TEXT_SUB,
            ).grid(row=0, column=2, sticky="e")
            for row, job in enumerate(jobs, start=1):
                self._row(
                    row - 1,
                    job,
                    active=(job.job_id == active_job_id),
                    can_move_up=(row > 1),
                    can_move_down=(row < len(jobs)),
                )

        counts = self.batch.counts()
        waiting = counts.get(JobStatus.WAITING, 0)
        self.summary.configure(
            text=(
                f"Totalt: {len(jobs)}   |   Ferdig: {counts[JobStatus.OK]}   |   "
                f"Kjører: {counts[JobStatus.RUNNING]}   |   Venter: {waiting}   |   "
                f"Klar: {counts[JobStatus.READY]}   |   Feil: {counts[JobStatus.FAILED]}   |   "
                f"Hoppet over: {counts[JobStatus.SKIPPED]}"
            )
        )
        self.set_batch_running(self._batch_running)

    def _row(
        self,
        row: int,
        job: Job,
        *,
        active: bool = False,
        can_move_up: bool = True,
        can_move_down: bool = True,
    ) -> None:
        card_color = theme.BLUE_DIM if active else theme.CARD_BG
        card = ctk.CTkFrame(self.list_frame, fg_color=card_color, corner_radius=6)
        card.grid(row=row, column=0, padx=5, pady=4, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        status_color = theme.BLUE if job.status == JobStatus.RUNNING else theme.TEXT_SUB
        if job.status == JobStatus.FAILED:
            status_color = theme.DANGER_TEXT

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, padx=8, pady=(7, 0), sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        selected = job.job_id in self._selected_job_ids_for_run()
        check = ctk.CTkCheckBox(
            top,
            text="",
            width=20,
            variable=ctk.BooleanVar(value=selected),
            command=lambda jid=job.job_id: self._toggle_selection(jid),
        )
        check.grid(row=0, column=0, padx=(0, 8), sticky="w")

        id_text = f"{job.job_id}  • AKTIV" if active else job.job_id
        id_color = theme.BLUE if active else theme.TEXT_SUB
        ctk.CTkLabel(
            top, text=id_text, width=130, anchor="w",
            font=theme.font(theme.SMALL_SIZE, "bold"), text_color=id_color,
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")

        ctk.CTkLabel(
            top, text=job.name, anchor="w",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.BLUE if active else theme.TEXT_SUB,
        ).grid(row=0, column=2, sticky="ew")

        status_text = job.status.value
        if job.status == JobStatus.READY and job.message == _CHANGED_AFTER_RUN:
            status_text = "Klar – endret etter kjøring"

        ctk.CTkLabel(
            top, text=status_text, width=185, anchor="w",
            font=theme.font(theme.SMALL_SIZE), text_color=status_color
        ).grid(row=0, column=3, padx=8, sticky="w")
        ctk.CTkLabel(
            top, text=f"{job.progress:.0%}", width=55, font=theme.font(theme.SMALL_SIZE)
        ).grid(row=0, column=4, padx=8)
        ctk.CTkLabel(
            top, text=job.worker, width=145, anchor="w",
            font=theme.font(theme.SMALL_SIZE)
        ).grid(row=0, column=5, padx=8, sticky="w")

        state = "disabled" if self._batch_running else "normal"
        ctk.CTkButton(
            top, text="↑", width=32, height=27,
            state=state if can_move_up else "disabled",
            command=lambda j=job: self._move_up(j),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER
        ).grid(row=0, column=6, padx=(6, 2))
        ctk.CTkButton(
            top, text="↓", width=32, height=27,
            state=state if can_move_down else "disabled",
            command=lambda j=job: self._move_down(j),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER
        ).grid(row=0, column=7, padx=2)
        ctk.CTkButton(
            top, text="Slett", width=58, height=27, state=state,
            command=lambda j=job: self._delete(j),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER
        ).grid(row=0, column=8, padx=2)
        ctk.CTkButton(
            top, text="Åpne", width=70, height=27, state="normal",
            command=lambda j=job: self._open(j),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER
        ).grid(row=0, column=9, padx=(2, 0))

        details = ctk.CTkFrame(card, fg_color="transparent")
        details.grid(row=1, column=0, columnspan=2, padx=8, pady=(2, 7), sticky="ew")
        details.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            details, text=f"Kilde: {job.source_root}", anchor="w",
            font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MUTED
        ).grid(row=0, column=0, padx=(0, 18), sticky="w")
        ctk.CTkLabel(
            details, text=f"Utdata: {job.output_root or '(ikke valgt)'}", anchor="w",
            font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_MUTED
        ).grid(row=0, column=1, sticky="ew")
        if job.message:
            ctk.CTkLabel(
                details, text=job.message, anchor="w",
                font=theme.font(theme.SMALL_SIZE), text_color=theme.TEXT_SUB
            ).grid(row=1, column=0, columnspan=2, pady=(2, 0), sticky="ew")
