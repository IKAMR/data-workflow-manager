from __future__ import annotations

from typing import Callable, Iterable

import customtkinter as ctk

from noark5_workflow.extraction_discovery import ExtractionCandidate
from . import theme


class ExtractionCandidateSelectionDialog(ctk.CTkToplevel):
    """Select which discovered extractions should become jobs.

    All candidates are selected by default. The checklist is deliberately built
    from explicit row frames with a separate checkbox and label. This avoids the
    blank-list rendering observed with long path text directly inside
    CTkCheckBox on the current Windows/CustomTkinter runtime.
    """

    def __init__(
        self,
        master,
        candidates: Iterable[ExtractionCandidate],
        *,
        extraction_label: str,
        source_label: str,
        on_confirm: Callable[[tuple[ExtractionCandidate, ...]], None],
    ) -> None:
        super().__init__(master)
        self._candidates = tuple(candidates)
        self._on_confirm = on_confirm
        self._vars: list[ctk.BooleanVar] = []

        self.title(f"Velg {extraction_label}-uttrekk")
        self.geometry("980x650")
        self.minsize(760, 480)
        self.configure(fg_color=theme.APP_BG)
        self.transient(master)

        ctk.CTkLabel(
            self,
            text="VELG UTTREKK",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
        ).pack(anchor="w", padx=22, pady=(20, 4))

        ctk.CTkLabel(
            self,
            text=(
                f"{len(self._candidates)} {extraction_label}-uttrekk funnet. "
                "Alle er valgt som standard."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=22, pady=(0, 4))

        ctk.CTkLabel(
            self,
            text=f"Kilde: {source_label}",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=900,
        ).pack(anchor="w", padx=22, pady=(0, 12))

        # Keep all selection actions above the list so they remain visible even
        # if the scrollable area requests more vertical space than expected.
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=22, pady=(0, 10))
        ctk.CTkButton(
            toolbar,
            text="Velg alle",
            command=self._select_all,
            width=110,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            toolbar,
            text="Tøm",
            command=self._clear_all,
            width=90,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).pack(side="left")

        self._confirm_button = ctk.CTkButton(
            toolbar,
            text="Legg til valgte",
            command=self._confirm,
            width=150,
        )
        self._confirm_button.pack(side="right")
        self._count_label = ctk.CTkLabel(
            toolbar,
            text="",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_MUTED,
        )
        self._count_label.pack(side="right", padx=(0, 14))

        listing = ctk.CTkScrollableFrame(
            self,
            fg_color=theme.PANEL_BG,
            corner_radius=6,
        )
        listing.pack(fill="both", expand=True, padx=22, pady=(0, 12))

        for index, candidate in enumerate(self._candidates, start=1):
            var = ctk.BooleanVar(value=True)
            self._vars.append(var)

            row = ctk.CTkFrame(listing, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=3)
            row.grid_columnconfigure(1, weight=1)

            checkbox = ctk.CTkCheckBox(
                row,
                text="",
                variable=var,
                command=self._refresh_count,
                width=28,
                checkbox_width=20,
                checkbox_height=20,
            )
            checkbox.grid(row=0, column=0, sticky="nw", padx=(2, 8), pady=7)

            name = candidate.suggested_name or candidate.path.name or str(candidate.path)
            path = str(candidate.path)
            text = f"{index}. {name}\n{path}"
            label = ctk.CTkLabel(
                row,
                text=text,
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT,
                anchor="w",
                justify="left",
                wraplength=830,
            )
            label.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=5)

            # Clicking the text should toggle the same checkbox, not only the
            # small square at the left edge.
            label.bind("<Button-1>", lambda _event, v=var: self._toggle(v))
            row.bind("<Button-1>", lambda _event, v=var: self._toggle(v))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=22, pady=(0, 18))
        ctk.CTkButton(
            footer,
            text="Avbryt",
            command=self.destroy,
            width=100,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).pack(side="right")

        self._refresh_count()
        self.after_idle(self._present)

    def _toggle(self, var: ctk.BooleanVar) -> None:
        var.set(not bool(var.get()))
        self._refresh_count()

    def _select_all(self) -> None:
        for var in self._vars:
            var.set(True)
        self._refresh_count()

    def _clear_all(self) -> None:
        for var in self._vars:
            var.set(False)
        self._refresh_count()

    def _selected(self) -> tuple[ExtractionCandidate, ...]:
        return tuple(
            candidate
            for candidate, var in zip(self._candidates, self._vars)
            if bool(var.get())
        )

    def _refresh_count(self) -> None:
        selected = len(self._selected())
        self._count_label.configure(text=f"Valgt: {selected} av {len(self._candidates)}")
        self._confirm_button.configure(state="normal" if selected else "disabled")

    def _confirm(self) -> None:
        selected = self._selected()
        if not selected:
            return
        self.destroy()
        self._on_confirm(selected)

    def _present(self) -> None:
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass
