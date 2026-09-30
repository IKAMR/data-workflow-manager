from __future__ import annotations

import customtkinter as ctk

from noark5_workflow.extraction_discovery import ExtractionTypeDefinition
from . import theme


class ExtractionDiscoveryDialog(ctk.CTkToplevel):
    """Generic chooser for extraction type and discovery source."""

    def __init__(
        self,
        master,
        definitions: tuple[ExtractionTypeDefinition, ...],
        *,
        initial_type_id: str = "",
        on_folders=None,
        on_lists=None,
    ) -> None:
        super().__init__(master)
        self.definitions = definitions
        self.on_folders = on_folders or (lambda _type_id: None)
        self.on_lists = on_lists or (lambda _type_id: None)
        self.title("Finn uttrekk")
        self.geometry("520x245")
        self.resizable(False, False)
        self.configure(fg_color=theme.APP_BG)
        self.transient(master)

        by_id = {item.type_id: item for item in definitions}
        labels = [item.label for item in definitions]
        chosen = by_id.get(initial_type_id) or (definitions[0] if definitions else None)
        self._label_to_id = {item.label: item.type_id for item in definitions}
        self.type_var = ctk.StringVar(value=chosen.label if chosen else "")

        ctk.CTkLabel(
            self,
            text="FINN UTTREKK",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
        ).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(
            self,
            text="Velg uttrekkstype og hvor søkegrunnlaget kommer fra.",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=22, pady=(0, 14))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=(0, 18))
        ctk.CTkLabel(
            row,
            text="Uttrekkstype",
            width=110,
            anchor="w",
            font=theme.font(theme.SMALL_SIZE, "bold"),
        ).pack(side="left")
        ctk.CTkOptionMenu(
            row,
            variable=self.type_var,
            values=labels,
            width=250,
        ).pack(side="left", padx=(8, 0))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=22, pady=(0, 8))
        ctk.CTkButton(
            actions,
            text="Søk i mapper...",
            command=self._folders,
            width=150,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            actions,
            text="Søk fra liste...",
            command=self._lists,
            width=150,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Lukk",
            command=self.destroy,
            width=90,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).pack(side="right")

        self.after_idle(self._present)

    def _type_id(self) -> str:
        return self._label_to_id.get(self.type_var.get(), "")

    def _folders(self) -> None:
        type_id = self._type_id()
        self.destroy()
        if type_id:
            self.on_folders(type_id)

    def _lists(self) -> None:
        type_id = self._type_id()
        self.destroy()
        if type_id:
            self.on_lists(type_id)

    def _present(self) -> None:
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass
