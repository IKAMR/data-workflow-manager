from __future__ import annotations

from typing import Callable, Iterable

import customtkinter as ctk

from noark5_workflow.core.job import Job
from noark5_workflow.job_batch_actions import StorageSuggestionPreviewJob
from . import theme


_ROLE_LABELS = {
    "source_root": "Source root",
    "source_tar": "Source TAR",
    "source_unzipped": "Source unpacked",
    "source_extraction": "Source extraction",
    "work_root": "Work root",
    "work_content": "Work content",
    "work_operations": "Work operations",
    "archive_root": "Storage root",
}


class StorageSuggestionPreviewDialog(ctk.CTkToplevel):
    """Preview per-job storage suggestions before applying anything."""

    def __init__(
        self,
        master,
        rows: Iterable[tuple[Job, StorageSuggestionPreviewJob]],
        *,
        on_apply: Callable[[tuple[Job, ...]], None],
    ) -> None:
        super().__init__(master)
        self._rows = tuple(rows)
        self._on_apply = on_apply
        self._vars: list[tuple[Job, ctk.BooleanVar]] = []

        self.title("Forhåndsvis mappeforslag")
        self.geometry("1120x760")
        self.minsize(860, 560)
        self.configure(fg_color=theme.APP_BG)
        self.transient(master)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            self,
            text="MAPPEFORSLAG",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
            anchor="w",
        ).grid(row=0, column=0, padx=24, pady=(22, 6), sticky="ew")

        ctk.CTkLabel(
            self,
            text=(
                "Kontroller hvilke jobber som skal få beregnede mappeforslag. "
                "Alle er valgt som standard. Eksisterende mappevalg overskrives ikke."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
            wraplength=1050,
        ).grid(row=1, column=0, padx=24, pady=(0, 12), sticky="ew")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=2, column=0, padx=24, pady=(0, 8), sticky="ew")
        toolbar.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(
            toolbar, text="Alle", width=90, fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER, command=self._select_all,
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            toolbar, text="Ingen", width=90, fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER, command=self._clear_all,
        ).grid(row=0, column=1, sticky="w")
        self._count = ctk.CTkLabel(
            toolbar, text="", font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
        )
        self._count.grid(row=0, column=3, padx=(12, 16), sticky="e")
        self._apply = ctk.CTkButton(
            toolbar, text="Bruk forslag", width=130, fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE, command=self._apply_selected,
        )
        self._apply.grid(row=0, column=4, sticky="e")

        ctk.CTkLabel(
            self, text="Forslag per jobb", font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB, anchor="w",
        ).grid(row=3, column=0, padx=24, pady=(6, 6), sticky="ew")

        scroll = ctk.CTkScrollableFrame(self, fg_color=theme.PANEL_BG)
        scroll.grid(row=4, column=0, padx=24, pady=(0, 14), sticky="nsew")
        scroll.grid_columnconfigure(1, weight=1)

        for row_no, (job, preview) in enumerate(self._rows):
            selectable = bool(preview.fillable)
            var = ctk.BooleanVar(value=selectable)
            self._vars.append((job, var))
            check = ctk.CTkCheckBox(
                scroll, text="", variable=var, width=28,
                state="normal" if selectable else "disabled",
                command=self._update_count,
            )
            check.grid(row=row_no, column=0, padx=(10, 8), pady=10, sticky="nw")

            if preview.fillable:
                detail = " | ".join(
                    f"{_ROLE_LABELS.get(attr, attr)} -> {path}"
                    for attr, path in preview.fillable
                )
            else:
                detail = "Ingen tomme mappefelt kan fylles fra gjeldende mappeprofil."
            text = f"{job.job_id}   {job.name or job.job_id}\n{detail}"
            label = ctk.CTkLabel(
                scroll, text=text, font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MAIN if selectable else theme.TEXT_MUTED,
                justify="left", anchor="w", wraplength=1000,
            )
            label.grid(row=row_no, column=1, padx=(0, 12), pady=8, sticky="ew")
            if selectable:
                label.bind("<Button-1>", lambda _e, v=var: self._toggle(v))

        ctk.CTkButton(
            self, text="Avbryt", width=100, fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER, command=self.destroy,
        ).grid(row=5, column=0, padx=24, pady=(0, 18), sticky="e")
        self._update_count()

    def _toggle(self, var: ctk.BooleanVar) -> None:
        var.set(not bool(var.get()))
        self._update_count()

    def _select_all(self) -> None:
        fillable_ids = {job.job_id for job, preview in self._rows if preview.fillable}
        for job, var in self._vars:
            var.set(job.job_id in fillable_ids)
        self._update_count()

    def _clear_all(self) -> None:
        for _job, var in self._vars:
            var.set(False)
        self._update_count()

    def _selected(self) -> tuple[Job, ...]:
        return tuple(job for job, var in self._vars if bool(var.get()))

    def _update_count(self) -> None:
        selected = len(self._selected())
        available = sum(bool(preview.fillable) for _job, preview in self._rows)
        self._count.configure(text=f"Valgt: {selected} av {available}")
        self._apply.configure(state="normal" if selected else "disabled")

    def _apply_selected(self) -> None:
        selected = self._selected()
        if not selected:
            return
        self._on_apply(selected)
        self.destroy()
