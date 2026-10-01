from __future__ import annotations

from typing import Callable, Iterable

import customtkinter as ctk

from noark5_workflow.external_evidence.arkade5_discovery import Arkade5Candidate
from noark5_workflow.job_batch_actions import (
    Arkade5DiscoveryBatchResult,
    Arkade5DiscoveryImportState,
)
from . import theme


class Arkade5BatchDiscoveryDialog(ctk.CTkToplevel):
    """Review correlated Arkade 5 reports with visible import state."""

    def __init__(
        self,
        master,
        result: Arkade5DiscoveryBatchResult,
        *,
        import_states: Iterable[Arkade5DiscoveryImportState] = (),
        on_accept: Callable[
            [tuple[tuple[str, Arkade5Candidate], ...]],
            Iterable[tuple[str, str]] | None,
        ] | None = None,
    ) -> None:
        super().__init__(master)
        self._result = result
        self._on_accept = on_accept
        self._state_by_key = {
            (row.job_id, str(row.sha256 or "").casefold()): row.status
            for row in import_states
        }
        self._vars: list[tuple[str, Arkade5Candidate, ctk.BooleanVar, object | None]] = []
        self._status_labels: dict[tuple[str, str], object] = {}
        self._imported_icons: dict[tuple[str, str], object] = {}

        self.title("Arkade 5-resultater")
        self.geometry("1180x800")
        self.minsize(920, 600)
        self.configure(fg_color=theme.APP_BG)
        self.transient(master)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            self,
            text="ARKADE 5-RESULTATER",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
            anchor="w",
        ).grid(row=0, column=0, padx=24, pady=(22, 6), sticky="ew")

        self._summary = ctk.CTkLabel(
            self,
            text="",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
            anchor="w",
        )
        self._summary.grid(row=1, column=0, padx=24, pady=(0, 4), sticky="ew")

        ctk.CTkLabel(
            self,
            text=(
                "Kontroller treffene før import. Bare rapporter som kobles entydig til en jobb vises her. Nye rapporter er valgt som standard. "
                "Rapporter med identisk SHA-256 som allerede er importert til jobben "
                "vises som «Allerede importert» og er ikke valgt på nytt. Import bevarer originalrapporten."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
            wraplength=1100,
        ).grid(row=2, column=0, padx=24, pady=(0, 10), sticky="ew")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=3, column=0, padx=24, pady=(0, 8), sticky="ew")
        toolbar.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(
            toolbar,
            text="Alle nye",
            width=100,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._select_all,
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            toolbar,
            text="Ingen",
            width=90,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._clear_all,
        ).grid(row=0, column=1, sticky="w")
        self._count = ctk.CTkLabel(
            toolbar,
            text="",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
        )
        self._count.grid(row=0, column=3, padx=(12, 16), sticky="e")
        self._accept = ctk.CTkButton(
            toolbar,
            text="Importer nye valgte",
            width=170,
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
            command=self._accept_selected,
        )
        self._accept.grid(row=0, column=4, sticky="e")

        scroll = ctk.CTkScrollableFrame(self, fg_color=theme.PANEL_BG)
        scroll.grid(row=4, column=0, padx=24, pady=(0, 14), sticky="nsew")
        scroll.grid_columnconfigure(1, weight=1)
        row_no = 0

        for job_result in result.job_results:
            if job_result.error:
                status = f"Feil: {job_result.error}"
                color = theme.TEXT_MUTED
            elif job_result.candidates:
                status = f"{len(job_result.candidates)} rapport(er) koblet"
                color = theme.BLUE
            else:
                status = "Ingen entydig Arkade 5-rapport funnet"
                color = theme.TEXT_MUTED

            ctk.CTkLabel(
                scroll,
                text=f"{job_result.job_id}   {job_result.job_name}   —   {status}",
                font=theme.font(theme.SMALL_SIZE, "bold"),
                text_color=color,
                anchor="w",
            ).grid(row=row_no, column=0, columnspan=2, padx=12, pady=(10, 3), sticky="ew")
            row_no += 1

            for candidate in job_result.candidates:
                key = self._key(job_result.job_id, candidate)
                imported = self._state_by_key.get(key) == "already_imported"
                var = ctk.BooleanVar(value=not imported)
                checkbox = None
                if imported:
                    # Informational status icon, deliberately not interactive.
                    imported_icon = ctk.CTkLabel(
                        scroll,
                        text="✓",
                        width=28,
                        font=theme.font(theme.BODY_SIZE, "bold"),
                        text_color=theme.BLUE,
                        anchor="center",
                    )
                    imported_icon.grid(row=row_no, column=0, padx=(18, 8), pady=7, sticky="nw")
                    self._imported_icons[key] = imported_icon
                else:
                    checkbox = ctk.CTkCheckBox(
                        scroll,
                        text="",
                        variable=var,
                        width=28,
                        command=self._update_count,
                    )
                    checkbox.grid(row=row_no, column=0, padx=(18, 8), pady=7, sticky="nw")
                self._vars.append((job_result.job_id, candidate, var, checkbox))

                state_text = "Allerede importert" if imported else "Ny"
                state_label = ctk.CTkLabel(
                    scroll,
                    text=state_text,
                    font=theme.font(theme.SMALL_SIZE, "bold"),
                    text_color=theme.TEXT_MUTED if imported else theme.BLUE,
                    anchor="w",
                )
                state_label.grid(row=row_no, column=1, padx=(0, 12), pady=(5, 0), sticky="nw")
                self._status_labels[key] = state_label

                details = (
                    f"\n{candidate.path}\n"
                    f"Dato: {candidate.test_date or '-'}   "
                    f"Tester: {candidate.tests_run}   "
                    f"Feil: {candidate.errors}   "
                    f"Advarsler: {candidate.warnings}"
                )
                label = ctk.CTkLabel(
                    scroll,
                    text=details,
                    font=theme.font(theme.SMALL_SIZE),
                    text_color=theme.TEXT_MUTED if imported else theme.TEXT_MAIN,
                    justify="left",
                    anchor="w",
                    wraplength=1020,
                )
                label.grid(row=row_no, column=1, padx=(0, 12), pady=(0, 7), sticky="ew")
                if not imported:
                    label.bind("<Button-1>", lambda _e, v=var: self._toggle(v))
                row_no += 1

        ctk.CTkButton(
            self,
            text="Lukk",
            width=100,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self.destroy,
        ).grid(row=5, column=0, padx=24, pady=(0, 18), sticky="e")
        self._update_count()

    @staticmethod
    def _key(job_id: str, candidate: Arkade5Candidate) -> tuple[str, str]:
        return (job_id, str(candidate.sha256 or "").casefold())

    def _is_new(self, job_id: str, candidate: Arkade5Candidate) -> bool:
        return self._state_by_key.get(self._key(job_id, candidate), "new") != "already_imported"

    def _toggle(self, var: ctk.BooleanVar) -> None:
        var.set(not bool(var.get()))
        self._update_count()

    def _select_all(self) -> None:
        for job_id, candidate, var, _checkbox in self._vars:
            var.set(self._is_new(job_id, candidate))
        self._update_count()

    def _clear_all(self) -> None:
        for _job_id, _candidate, var, _checkbox in self._vars:
            var.set(False)
        self._update_count()

    def _selected(self) -> tuple[tuple[str, Arkade5Candidate], ...]:
        return tuple(
            (job_id, candidate)
            for job_id, candidate, var, _checkbox in self._vars
            if bool(var.get()) and self._is_new(job_id, candidate)
        )

    def _counts(self) -> tuple[int, int]:
        total = len(self._vars)
        already = sum(
            not self._is_new(job_id, candidate)
            for job_id, candidate, _var, _checkbox in self._vars
        )
        return total - already, already

    def _update_count(self) -> None:
        selected = len(self._selected())
        new_count, already = self._counts()
        self._count.configure(text=f"Valgt nye: {selected} av {new_count}")
        self._summary.configure(
            text=(
                f"Valgte jobber: {self._result.selected_jobs}   |   "
                f"Rapporter koblet: {self._result.reports_found}   |   "
                f"Nye: {new_count}   |   Allerede importert: {already}   |   "
                f"Ufordelte rapporter: {self._result.unmatched_reports}   |   "
                f"Feil: {self._result.failed_jobs}"
            )
        )
        self._accept.configure(
            state="normal" if selected and self._on_accept is not None else "disabled"
        )

    def _mark_imported(self, keys: Iterable[tuple[str, str]]) -> None:
        changed = set(keys)
        if not changed:
            return
        for job_id, candidate, var, checkbox in self._vars:
            key = self._key(job_id, candidate)
            if key not in changed:
                continue
            self._state_by_key[key] = "already_imported"
            var.set(False)
            if checkbox is not None:
                try:
                    checkbox_row = checkbox.grid_info().get("row", 0)
                except Exception:
                    checkbox_row = 0
                try:
                    checkbox.destroy()
                except Exception:
                    pass
                try:
                    imported_icon = ctk.CTkLabel(
                        checkbox.master,
                        text="✓",
                        width=28,
                        font=theme.font(theme.BODY_SIZE, "bold"),
                        text_color=theme.BLUE,
                        anchor="center",
                    )
                    imported_icon.grid(
                        row=checkbox_row,
                        column=0,
                        padx=(18, 8),
                        pady=7,
                        sticky="nw",
                    )
                    self._imported_icons[key] = imported_icon
                except Exception:
                    pass
            label = self._status_labels.get(key)
            if label is not None:
                try:
                    label.configure(text="Allerede importert", text_color=theme.TEXT_MUTED)
                except Exception:
                    pass
        self._update_count()

    def _accept_selected(self) -> None:
        selected = self._selected()
        if not selected or self._on_accept is None:
            return
        imported_keys = self._on_accept(selected)
        if imported_keys is not None:
            self._mark_imported(imported_keys)
