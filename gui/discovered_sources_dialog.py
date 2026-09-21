from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox

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
        result_inventory_provider=None,
    ) -> None:
        super().__init__(master)
        self.candidates = list(candidates)
        self.existing_sources = {
            value.replace("/", "\\").rstrip("\\").casefold()
            for value in (existing_sources or set())
        }
        self.result_inventory_provider = result_inventory_provider
        self.selected: list[DiscoveredSource] | None = None
        self.check_existing_results = False
        self.reset_execution_state = False
        self.inventories: dict[str, object] = {}
        self._vars: list[tuple[DiscoveredSource, tk.BooleanVar, bool]] = []
        self._inventory_labels: dict[str, ctk.CTkLabel] = {}

        self.title("Finn Noark 5-jobber")
        self.geometry("1540x820")
        self.minsize(1080, 620)
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
        body.grid_columnconfigure(5, weight=1)

        headers = (
            "Velg", "Foreslått jobb", "Noark 5-rot", "Status", "Grunnlag",
            "Eksisterende resultater",
        )
        for col, label in enumerate(headers):
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

            inventory_label = ctk.CTkLabel(
                body, text="Ikke kontrollert",
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MUTED, anchor="w",
            )
            inventory_label.grid(row=row, column=5, padx=6, pady=4, sticky="ew")
            self._inventory_labels[self._key(candidate.path)] = inventory_label

        options = ctk.CTkFrame(self, fg_color=theme.PANEL_BG_DARK, corner_radius=8)
        options.grid(row=3, column=0, padx=18, pady=(0, 8), sticky="ew")
        options.grid_columnconfigure(2, weight=1)

        self.check_results_var = tk.BooleanVar(value=False)
        self.reset_state_var = tk.BooleanVar(value=False)

        ctk.CTkCheckBox(
            options,
            text="Kontroller eksisterende resultater i Work - operations",
            variable=self.check_results_var,
            command=self._check_option_changed,
        ).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        self.reset_checkbox = ctk.CTkCheckBox(
            options,
            text="Nullstill kjørestatus/cursor (krever bekreftelse; sletter ikke resultater/logger)",
            variable=self.reset_state_var,
            state="disabled",
        )
        self.reset_checkbox.grid(row=0, column=1, padx=12, pady=8, sticky="w")

        self.scan_button = ctk.CTkButton(
            options,
            text="Kontroller nå",
            width=110,
            command=self._scan_results,
            state="disabled",
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self.scan_button.grid(row=0, column=3, padx=12, pady=8, sticky="e")

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=4, column=0, padx=18, pady=(4, 6), sticky="ew")

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
        found_results = sum(
            1 for inventory in self.inventories.values()
            if getattr(inventory, "has_results", False)
        )
        text = f"Funnet: {len(self._vars)}   |   Valgt: {selected}"
        if duplicates:
            text += f"   |   Allerede i jobbliste: {duplicates}"
        if self.inventories:
            text += f"   |   Med eksisterende resultater: {found_results}"
        self.summary.configure(text=text)
        self.add_button.configure(state="normal" if selected else "disabled")

    def _check_option_changed(self) -> None:
        enabled = bool(self.check_results_var.get())
        self.scan_button.configure(state="normal" if enabled else "disabled")
        self.reset_checkbox.configure(state="normal" if enabled else "disabled")
        if not enabled:
            self.reset_state_var.set(False)

    def _scan_results(self) -> None:
        if not self.check_results_var.get():
            return
        if not callable(self.result_inventory_provider):
            return

        self.scan_button.configure(state="disabled", text="Kontrollerer...")
        self.update_idletasks()
        try:
            for candidate, _variable, _duplicate in self._vars:
                key = self._key(candidate.path)
                try:
                    inventory = self.result_inventory_provider(candidate)
                    self.inventories[key] = inventory
                    text = getattr(inventory, "summary", "Ukjent")
                except Exception as exc:
                    text = f"Kontrollfeil: {exc}"
                label = self._inventory_labels.get(key)
                if label is not None:
                    label.configure(text=text)
        finally:
            self.scan_button.configure(state="normal", text="Kontroller nå")
            self._refresh_summary()

    def _accept(self) -> None:
        if self.check_results_var.get() and not self.inventories:
            self._scan_results()

        selected = [
            candidate for candidate, variable, duplicate in self._vars
            if variable.get() and not duplicate
        ]
        if not selected:
            return

        wants_reset = bool(
            self.check_results_var.get() and self.reset_state_var.get()
        )
        if wants_reset:
            if not messagebox.askyesno(
                "Noark 5 Workflow Manager",
                "Nullstille kjørestatus/cursor for valgte jobber?\n\n"
                "Dette setter jobbene klare for ny kjøring fra start. "
                "Eksisterende resultatfiler og logger på disk slettes ikke.\n\n"
                "Fortsette?",
                parent=self,
            ):
                return

        self.selected = selected
        self.check_existing_results = bool(self.check_results_var.get())
        self.reset_execution_state = wants_reset
        self.destroy()

    def _cancel(self) -> None:
        self.selected = None
        self.destroy()
