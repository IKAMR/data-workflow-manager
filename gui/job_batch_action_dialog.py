from __future__ import annotations

from typing import Callable, Iterable

import customtkinter as ctk

from noark5_workflow.core.job import Job
from . import theme


class JobBatchActionDialog(ctk.CTkToplevel):
    """Select jobs and run reusable batch actions without changing row layout."""

    def __init__(
        self,
        master,
        jobs: Iterable[Job],
        *,
        on_fill_storage_suggestions: Callable[[tuple[Job, ...]], None],
        on_discover_arkade5_results: Callable[[tuple[Job, ...]], None] | None = None,
        on_run_arkade5: Callable[[tuple[Job, ...]], None] | None = None,
    ) -> None:
        super().__init__(master)
        self._jobs = tuple(jobs)
        self._on_fill_storage_suggestions = on_fill_storage_suggestions
        self._on_discover_arkade5_results = on_discover_arkade5_results
        self._on_run_arkade5 = on_run_arkade5
        self._vars: list[tuple[Job, ctk.BooleanVar]] = []

        self.title("Handlinger for jobber")
        self.geometry("1040x720")
        self.minsize(820, 520)
        self.configure(fg_color=theme.APP_BG)
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(
            self,
            text="HANDLINGER FOR JOBBER",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
            anchor="w",
        ).grid(row=0, column=0, padx=24, pady=(22, 6), sticky="ew")

        ctk.CTkLabel(
            self,
            text=(
                "Velg hvilke jobber handlingen skal gjelde. Alle er valgt som standard. "
                "Handlingene bruker jobbens egne Source/Work-roller og endrer bare data "
                "når handlingen uttrykkelig sier det."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            justify="left",
            anchor="w",
            wraplength=960,
        ).grid(row=1, column=0, padx=24, pady=(0, 14), sticky="ew")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=2, column=0, padx=24, pady=(0, 8), sticky="ew")
        toolbar.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(
            toolbar,
            text="Velg alle",
            width=100,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._select_all,
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            toolbar,
            text="Tøm",
            width=80,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._clear_all,
        ).grid(row=0, column=1, sticky="w")

        self._count_label = ctk.CTkLabel(
            toolbar,
            text="",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
        )
        self._count_label.grid(row=0, column=3, padx=(12, 0), sticky="e")

        self._fill_button = ctk.CTkButton(
            toolbar,
            text="Fyll mappeforslag",
            width=150,
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
            command=self._run_fill_storage_suggestions,
        )
        self._fill_button.grid(row=0, column=4, padx=(18, 8), sticky="e")

        self._arkade_button = ctk.CTkButton(
            toolbar,
            text="Finn Arkade 5-resultater",
            width=180,
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
            command=self._run_discover_arkade5_results,
        )
        self._arkade_button.grid(row=0, column=5, padx=(0, 8), sticky="e")

        self._arkade_run_button = ctk.CTkButton(
            toolbar,
            text="Kjør Arkade 5…",
            width=150,
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
            command=self._run_arkade5,
        )
        self._arkade_run_button.grid(row=0, column=6, sticky="e")

        self._action_status = ctk.CTkLabel(
            self,
            text="",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self._action_status.grid(row=3, column=0, padx=24, pady=(0, 4), sticky="ew")

        ctk.CTkLabel(
            self,
            text="Valgte jobber",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
            anchor="w",
        ).grid(row=4, column=0, padx=24, pady=(6, 6), sticky="ew")

        scroll = ctk.CTkScrollableFrame(self, fg_color=theme.PANEL_BG)
        scroll.grid(row=5, column=0, padx=24, pady=(0, 14), sticky="nsew")
        scroll.grid_columnconfigure(1, weight=1)

        for row, job in enumerate(self._jobs):
            var = ctk.BooleanVar(value=True)
            self._vars.append((job, var))
            checkbox = ctk.CTkCheckBox(
                scroll,
                text="",
                variable=var,
                width=28,
                command=self._update_count,
            )
            checkbox.grid(row=row, column=0, padx=(10, 8), pady=9, sticky="nw")

            source = job.active_extraction_root
            source_text = str(source) if source is not None else "Ingen kilde valgt"
            name = str(job.name or job.job_id)
            label = ctk.CTkLabel(
                scroll,
                text=f"{job.job_id}   {name}\n{source_text}",
                font=theme.font(theme.SMALL_SIZE),
                justify="left",
                anchor="w",
                text_color=theme.TEXT_MAIN,
                wraplength=880,
            )
            label.grid(row=row, column=1, padx=(0, 12), pady=7, sticky="ew")
            label.bind("<Button-1>", lambda _event, v=var: self._toggle(v))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=6, column=0, padx=24, pady=(0, 18), sticky="e")
        ctk.CTkButton(
            footer,
            text="Lukk",
            width=100,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self.destroy,
        ).pack(side="right")

        self._update_count()

    def _toggle(self, var: ctk.BooleanVar) -> None:
        var.set(not bool(var.get()))
        self._update_count()

    def _select_all(self) -> None:
        for _job, var in self._vars:
            var.set(True)
        self._update_count()

    def _clear_all(self) -> None:
        for _job, var in self._vars:
            var.set(False)
        self._update_count()

    def _selected(self) -> tuple[Job, ...]:
        return tuple(job for job, var in self._vars if bool(var.get()))

    def _update_count(self) -> None:
        count = len(self._selected())
        total = len(self._vars)
        self._count_label.configure(text=f"Valgt: {count} av {total}")
        state = "normal" if count else "disabled"
        self._fill_button.configure(state=state)
        self._arkade_button.configure(
            state=state if self._on_discover_arkade5_results is not None else "disabled"
        )
        self._arkade_run_button.configure(
            state=state if self._on_run_arkade5 is not None else "disabled"
        )

    def _run_fill_storage_suggestions(self) -> None:
        selected = self._selected()
        if not selected:
            return
        self._on_fill_storage_suggestions(selected)
        self._update_count()

    def _run_discover_arkade5_results(self) -> None:
        selected = self._selected()
        if not selected or self._on_discover_arkade5_results is None:
            return
        self._action_status.configure(
            text=(
                f"Søker etter Arkade 5-resultater for {len(selected)} jobb(er) … "
                "Dette kan ta litt tid på store eller langsomme lagringsområder."
            )
        )
        self._fill_button.configure(state="disabled")
        self._arkade_button.configure(state="disabled")
        self.update_idletasks()
        try:
            self._on_discover_arkade5_results(selected)
            self._action_status.configure(text="Arkade 5-søket er ferdig.")
        finally:
            self._update_count()

    def _run_arkade5(self) -> None:
        selected = self._selected()
        if not selected or self._on_run_arkade5 is None:
            return
        self._on_run_arkade5(selected)
