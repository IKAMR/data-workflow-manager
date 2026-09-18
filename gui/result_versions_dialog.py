from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import customtkinter as ctk

from noark5_workflow.core.result_review import ResultDisposition, ResultReviewLedger
from noark5_workflow.core.result_selection import (
    current_result,
    operation_results,
    review_ledger_path_for_job,
)
from . import theme


@dataclass(frozen=True)
class ResultVersionRow:
    result_id: str
    recorded_at: str
    ok: bool
    definition_version: str
    assessment: str
    current: bool
    reason: str


def result_version_rows(job, operation_id: str) -> list[ResultVersionRow]:
    """Return all persisted result versions for one stable operation id.

    Raw results remain append-only. Review state is resolved from the latest
    assessment event for each result_id. For legacy results with no assessment,
    the current result resolver still identifies the implicit current version.
    """
    items = operation_results(job, operation_id)
    current = current_result(job, operation_id)
    current_id = current.result_id if current is not None else ""

    latest = {}
    ledger_path = review_ledger_path_for_job(job)
    if ledger_path is not None and Path(ledger_path).is_file():
        latest = ResultReviewLedger(ledger_path).latest_by_result_id()

    rows: list[ResultVersionRow] = []
    for item in items:
        event = latest.get(item.result_id)
        if event is None:
            assessment = "legacy / ikke eksplisitt vurdert"
            reason = ""
        else:
            assessment = event.assessment.disposition.value
            reason = event.assessment.reason
        rows.append(
            ResultVersionRow(
                result_id=item.result_id,
                recorded_at=item.recorded_at,
                ok=bool(item.ok),
                definition_version=str(item.definition_version or ""),
                assessment=assessment,
                current=item.result_id == current_id,
                reason=reason,
            )
        )
    return rows


class ResultVersionsDialog(ctk.CTkToplevel):
    """Read-only a14.4 view of result-version history for one operation."""

    def __init__(self, master, job, operation_id: str, operation_name: str) -> None:
        super().__init__(master)
        # Build the complete dialog while hidden. On Windows/CustomTkinter a
        # newly mapped CTkToplevel may otherwise be visible for one frame before
        # DPI/font scaling and requested geometry settle.
        self.withdraw()
        self.job = job
        self.operation_id = operation_id
        self.operation_name = operation_name
        self.title(f"Resultatversjoner – {operation_name}")
        self.geometry("1180x650")
        self.minsize(900, 480)
        self.configure(fg_color=theme.APP_BG)
        self.transient(master)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            self,
            text=f"RESULTATVERSJONER – {job.job_id}",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=0, column=0, padx=18, pady=(16, 3), sticky="w")

        ctk.CTkLabel(
            self,
            text=f"{operation_name}  |  operation_id: {operation_id}",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_SUB,
            anchor="w",
        ).grid(row=1, column=0, padx=18, pady=(0, 3), sticky="ew")

        self.summary = ctk.CTkLabel(
            self,
            text="",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.summary.grid(row=2, column=0, padx=18, pady=(0, 8), sticky="ew")

        self.items = ctk.CTkScrollableFrame(
            self, fg_color=theme.PANEL_BG_DARK, corner_radius=8
        )
        self.items.grid(row=3, column=0, padx=18, pady=4, sticky="nsew")
        self.items.grid_columnconfigure(4, weight=1)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=4, column=0, padx=18, pady=(8, 16), sticky="e")
        ctk.CTkButton(
            buttons,
            text="Oppdater",
            width=100,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self.refresh,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            buttons,
            text="Lukk",
            width=90,
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
            command=self.destroy,
        ).pack(side="left", padx=4)

        self.refresh()

        # Finalise fonts, requested sizes and scroll-frame layout before the
        # first visible frame, then make the already-final dialog modal.
        self.update_idletasks()
        self.deiconify()
        self.lift(master)
        self.grab_set()

    def refresh(self) -> None:
        for child in self.items.winfo_children():
            child.destroy()

        try:
            rows = result_version_rows(self.job, self.operation_id)
        except Exception as exc:
            self.summary.configure(text=f"Kunne ikke lese resultatversjoner: {exc}")
            return

        current_count = sum(1 for row in rows if row.current)
        review_count = sum(1 for row in rows if row.assessment == ResultDisposition.REQUIRES_REVIEW.value)
        self.summary.configure(
            text=(
                f"{len(rows)} versjon(er). Gjeldende: {current_count}. "
                f"Til vurdering: {review_count}. Historikken er append-only."
            )
        )

        headers = ("Gjeldende", "Tid", "Kjøring", "Definisjon", "Vurdering / result_id")
        for col, text in enumerate(headers):
            ctk.CTkLabel(
                self.items,
                text=text,
                font=theme.font(theme.SMALL_SIZE, "bold"),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).grid(row=0, column=col, padx=8, pady=(6, 4), sticky="ew")

        if not rows:
            ctk.CTkLabel(
                self.items,
                text="Ingen lagrede resultatversjoner for denne operasjonen.",
                font=theme.font(theme.NORMAL_SIZE),
                text_color=theme.TEXT_MUTED,
            ).grid(row=1, column=0, columnspan=5, padx=10, pady=28, sticky="w")
            return

        for row_no, row in enumerate(reversed(rows), start=1):
            current_text = "✓ GJELDENDE" if row.current else ""
            execution_text = "PASS" if row.ok else "FAIL"
            assessment_text = row.assessment
            if row.reason:
                assessment_text += f" – {row.reason}"
            assessment_text += f"\n{row.result_id}"
            values = (
                current_text,
                row.recorded_at,
                execution_text,
                row.definition_version or "–",
                assessment_text,
            )
            for col, value in enumerate(values):
                color = theme.TEXT_MAIN
                if col == 0 and row.current:
                    color = "#2fbf71"
                elif col == 2 and not row.ok:
                    color = "#ff4d4f"
                elif col == 4 and row.assessment == ResultDisposition.REQUIRES_REVIEW.value:
                    color = "#b77cff"
                ctk.CTkLabel(
                    self.items,
                    text=str(value),
                    font=theme.font(theme.SMALL_SIZE),
                    text_color=color,
                    anchor="w",
                    justify="left",
                    wraplength=520 if col == 4 else 0,
                ).grid(row=row_no, column=col, padx=8, pady=6, sticky="ew")
