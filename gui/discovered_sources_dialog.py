from __future__ import annotations

from pathlib import Path
import tkinter as tk

import customtkinter as ctk

from noark5_workflow.plugins.noark5.discovery import DiscoveredSource
from . import theme


class DiscoveredSourcesDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        candidates: list[DiscoveredSource],
        *,
        existing_sources: set[str] | None = None,
    ) -> None:
        super().__init__(master)
        self.candidates = list(candidates)
        self.existing_sources = {
            value.replace("/", "\\").rstrip("\\").casefold()
            for value in (existing_sources or set())
        }
        self.selected: list[DiscoveredSource] | None = None
        self._vars: list[tuple[DiscoveredSource, tk.BooleanVar, bool]] = []

        self.title("Finn Noark 5-jobber")
        self.geometry("1380x760")
        self.minsize(980, 560)
        self.configure(fg_color=theme.APP_BG)
        self.transient(master)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self,
            text="FUNNEDE NOARK 5-UTTREKK",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=0, column=0, padx=18, pady=(16, 2), sticky="w")

        self.summary = ctk.CTkLabel(
            self, text="", font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED, anchor="w",
        )
        self.summary.grid(row=1, column=0, padx=18, pady=(2, 8), sticky="ew")

        body = ctk.CTkScrollableFrame(
            self, fg_color=theme.PANEL_BG_DARK, corner_radius=8
        )
        body.grid(row=2, column=0, padx=18, pady=(0, 8), sticky="nsew")
        body.grid_columnconfigure(2, weight=1)

        for col, label in enumerate(("Velg", "Foreslått jobb", "Noark 5-rot", "Status", "Grunnlag")):
            ctk.CTkLabel(
                body, text=label, font=theme.font(theme.SMALL_SIZE, "bold"),
                text_color=theme.TEXT_SUB, anchor="w",
            ).grid(row=0, column=col, padx=6, pady=(4, 6), sticky="ew")

        for row, candidate in enumerate(self.candidates, start=1):
            duplicate = self._key(candidate.path) in self.existing_sources
            variable = tk.BooleanVar(value=(candidate.safe_default and not duplicate))
            self._vars.append((candidate, variable, duplicate))

            checkbox = ctk.CTkCheckBox(
                body, text="", variable=variable, width=28,
                command=self._refresh_summary,
            )
            checkbox.grid(row=row, column=0, padx=6, pady=4, sticky="w")
            if duplicate:
                checkbox.configure(state="disabled")

            ctk.CTkLabel(
                body, text=candidate.suggested_name,
                font=theme.font(theme.SMALL_SIZE, "bold"), anchor="w",
            ).grid(row=row, column=1, padx=6, pady=4, sticky="w")

            ctk.CTkLabel(
                body, text=str(candidate.path),
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MUTED, anchor="w",
            ).grid(row=row, column=2, padx=6, pady=4, sticky="ew")

            ctk.CTkLabel(
                body,
                text="Allerede i jobbliste" if duplicate else candidate.confidence,
                width=140, font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MUTED if duplicate else theme.TEXT_SUB,
                anchor="w",
            ).grid(row=row, column=3, padx=6, pady=4, sticky="w")

            ctk.CTkLabel(
                body, text=", ".join(candidate.evidence),
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MUTED, anchor="w",
            ).grid(row=row, column=4, padx=6, pady=4, sticky="w")

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=3, column=0, padx=18, pady=(4, 6), sticky="ew")

        ctk.CTkButton(
            controls, text="Velg alle", width=94, command=self._select_all,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            controls, text="Velg ingen", width=94, command=self._select_none,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            controls, text="Inverter valg", width=104, command=self._invert,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            controls, text="Avbryt", width=90, command=self._cancel,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).pack(side="right", padx=(4, 0))
        self.add_button = ctk.CTkButton(
            controls, text="Legg valgte til jobblisten", width=190,
            command=self._accept, fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
        )
        self.add_button.pack(side="right", padx=4)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._refresh_summary()
        self.after_idle(self._finish_open)

    @staticmethod
    def _key(path: Path) -> str:
        return str(path).replace("/", "\\").rstrip("\\").casefold()

    def _finish_open(self) -> None:
        try:
            self.grab_set()
            self.focus()
        except Exception:
            pass

    def _select_all(self) -> None:
        for _candidate, variable, duplicate in self._vars:
            if not duplicate:
                variable.set(True)
        self._refresh_summary()

    def _select_none(self) -> None:
        for _candidate, variable, _duplicate in self._vars:
            variable.set(False)
        self._refresh_summary()

    def _invert(self) -> None:
        for _candidate, variable, duplicate in self._vars:
            if not duplicate:
                variable.set(not variable.get())
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        selected = sum(
            1 for _candidate, variable, duplicate in self._vars
            if variable.get() and not duplicate
        )
        duplicates = sum(1 for _candidate, _variable, duplicate in self._vars if duplicate)
        text = f"Funnet: {len(self._vars)}   |   Valgt: {selected}"
        if duplicates:
            text += f"   |   Allerede i jobbliste: {duplicates}"
        self.summary.configure(text=text)
        self.add_button.configure(state="normal" if selected else "disabled")

    def _accept(self) -> None:
        self.selected = [
            candidate for candidate, variable, duplicate in self._vars
            if variable.get() and not duplicate
        ]
        self.destroy()

    def _cancel(self) -> None:
        self.selected = None
        self.destroy()
