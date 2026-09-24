
from __future__ import annotations

import customtkinter as ctk

from app.workflow_sequences import WorkflowSequence
from . import theme


class WorkflowProfilesDialog(ctk.CTkToplevel):
    """Choose a built-in or user-defined workflow sequence."""

    def __init__(
        self,
        master,
        sequences: list[WorkflowSequence],
        *,
        on_apply,
        on_delete,
    ) -> None:
        super().__init__(master)
        self.sequences = list(sequences)
        self.on_apply = on_apply
        self.on_delete = on_delete

        self.title("Workflowprofiler")
        self.geometry("720x460")
        self.minsize(640, 400)
        self.configure(fg_color=theme.APP_BG)
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self,
            text="WORKFLOWPROFILER",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=0, column=0, padx=18, pady=(16, 10), sticky="w")

        names = [self._label(seq) for seq in self.sequences]
        self.selected = ctk.StringVar(value=names[0] if names else "")

        self.menu = ctk.CTkOptionMenu(
            self,
            values=names or ["Ingen profiler"],
            variable=self.selected,
            command=lambda _value: self._refresh_details(),
        )
        self.menu.grid(row=1, column=0, padx=18, pady=(0, 10), sticky="ew")

        self.details = ctk.CTkTextbox(
            self,
            fg_color=theme.PANEL_BG_DARK,
            font=theme.font(theme.SMALL_SIZE),
            wrap="word",
        )
        self.details.grid(row=2, column=0, padx=18, pady=4, sticky="nsew")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=3, column=0, padx=18, pady=(10, 16), sticky="e")

        self.delete_button = ctk.CTkButton(
            buttons,
            text="Slett brukerprofil",
            width=140,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._delete,
        )
        self.delete_button.pack(side="left", padx=4)

        ctk.CTkButton(
            buttons,
            text="Bruk",
            width=100,
            command=self._apply,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            buttons,
            text="Lukk",
            width=90,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self.destroy,
        ).pack(side="left", padx=4)

        self._refresh_details()

    @staticmethod
    def _label(sequence: WorkflowSequence) -> str:
        suffix = "bruker" if sequence.is_custom else "standard"
        return f"{sequence.name} [{suffix}]"

    def _current(self) -> WorkflowSequence | None:
        value = self.selected.get()
        for sequence in self.sequences:
            if self._label(sequence) == value:
                return sequence
        return None

    def _refresh_details(self) -> None:
        sequence = self._current()
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")

        if sequence is None:
            self.details.insert("end", "Ingen workflowprofiler er tilgjengelige.")
            self.delete_button.configure(state="disabled")
        else:
            self.details.insert(
                "end",
                f"{sequence.name}\n\n"
                f"{sequence.description or '(ingen beskrivelse)'}\n\n"
                f"Operasjoner: {len(sequence.operation_ids)}\n"
                + "\n".join(
                    f"{index}. {operation_id}"
                    for index, operation_id in enumerate(sequence.operation_ids, start=1)
                ),
            )
            self.delete_button.configure(
                state="normal" if sequence.is_custom else "disabled"
            )

        self.details.configure(state="disabled")

    def _apply(self) -> None:
        sequence = self._current()
        if sequence is None:
            return
        if self.on_apply(sequence):
            self.destroy()

    def _delete(self) -> None:
        sequence = self._current()
        if sequence is None or not sequence.is_custom:
            return
        if self.on_delete(sequence):
            self.sequences = [
                item for item in self.sequences
                if item.sequence_id != sequence.sequence_id
            ]
            names = [self._label(seq) for seq in self.sequences]
            self.menu.configure(values=names or ["Ingen profiler"])
            self.selected.set(names[0] if names else "")
            self._refresh_details()
