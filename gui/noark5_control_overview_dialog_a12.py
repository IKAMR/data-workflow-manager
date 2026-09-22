from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from app.noark5_control_worklist import (
    filter_rows,
    load_control_overview,
    summary_text,
)
from noark5_workflow.analysis.depot_assessment import load_depot_assessment
from version import APP_NAME
from . import theme
from .direct_depot_assessment_dialog_a12 import DirectDepotAssessmentDialogA12


_STATUS_VALUES = ["Alle", "FEIL", "VURDER", "MANGLER", "UKJENT", "OK"]

_ASSESSMENT_LABELS = {
    "accepted": "Akseptert",
    "accepted_with_deviation": "Akseptert med avvik",
    "requires_clarification": "Krever avklaring",
    "new_extraction_required": "Nytt uttrekk kreves",
}


def _display(value) -> str:
    return "–" if value in (None, "") else str(value)


def _live_assessment_label(report_path: str | Path | None) -> str:
    if not report_path:
        return "–"
    try:
        stored = load_depot_assessment(Path(report_path))
    except Exception:
        return "–"
    if not stored or not stored.get("current"):
        return "Ikke vurdert"
    status = str((stored.get("current") or {}).get("status", "") or "")
    return _ASSESSMENT_LABELS.get(status, status or "Ikke vurdert")


class Noark5ControlOverviewDialogA11(ctk.CTkToplevel):
    """RUN-scoped Noark 5 worklist with direct depot assessment workflow."""

    def __init__(
        self,
        master,
        *,
        overview_json: str | Path,
        overview_html: str | Path | None = None,
        user_identity: dict[str, str] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Noark 5 kontrolloversikt")
        self.geometry("1580x840")
        self.minsize(1120, 670)
        self.transient(master)

        self.overview_json = Path(overview_json)
        self.overview_html = Path(overview_html) if overview_html else None
        self.user_identity = user_identity
        self.model = load_control_overview(self.overview_json)
        self._assessment_dialog = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="NOARK 5 KONTROLLOVERSIKT",
            anchor="w",
            font=theme.font(theme.TITLE_SIZE),
        ).grid(row=0, column=0, sticky="w")

        run_id = str(self.model.get("run_id", "") or "")
        generated = str(self.model.get("generated_at", "") or "")
        ctk.CTkLabel(
            header,
            text=f"RUN: {run_id}   |   Generert: {generated}",
            anchor="w",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.summary_var = ctk.StringVar(value=summary_text(self.model))
        ctk.CTkLabel(
            self,
            textvariable=self.summary_var,
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 4))

        ctk.CTkLabel(
            self,
            text=(
                "VURDER = teknisk kjøring er fullført, men ett eller flere forhold "
                "må vurderes faglig. Klikk Vurder for å åpne depotvurderingen for "
                "den eksakte rapporten i denne RUN-en."
            ),
            anchor="w",
            justify="left",
            wraplength=1500,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))

        controls = ctk.CTkFrame(self)
        controls.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 10))
        controls.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(controls, text="Status").grid(
            row=0, column=0, padx=(10, 6), pady=10
        )
        self.status_var = ctk.StringVar(value="Alle")
        ctk.CTkOptionMenu(
            controls,
            variable=self.status_var,
            values=_STATUS_VALUES,
            command=lambda _value: self._refresh_rows(),
            width=140,
        ).grid(row=0, column=1, sticky="w", padx=(0, 14), pady=10)

        self.search_entry = ctk.CTkEntry(
            controls,
            placeholder_text="Søk i jobb, navn, kilde eller statusmelding",
        )
        self.search_entry.grid(row=0, column=2, sticky="ew", padx=(0, 8), pady=10)
        self.search_entry.bind("<Return>", lambda _event: self._refresh_rows())
        self.search_entry.bind("<KeyRelease>", lambda _event: self._refresh_rows())

        ctk.CTkButton(
            controls,
            text="Nullstill filter",
            width=110,
            command=self._reset_filters,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=3, padx=(0, 8), pady=10)

        ctk.CTkButton(
            controls,
            text="HTML-oversikt",
            width=120,
            state="normal" if self.overview_html and self.overview_html.is_file() else "disabled",
            command=self._open_batch_html,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=4, padx=(0, 10), pady=10)

        self.rows_frame = ctk.CTkScrollableFrame(self)
        self.rows_frame.grid(row=4, column=0, sticky="nsew", padx=18, pady=(0, 10))
        for column, weight in enumerate((0, 2, 0, 0, 0, 0, 0, 0, 0, 0)):
            self.rows_frame.grid_columnconfigure(column, weight=weight)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)

        self.count_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            bottom,
            textvariable=self.count_var,
            anchor="w",
            text_color=theme.TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            bottom,
            text="Oppdater",
            width=90,
            command=self._refresh_rows,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            bottom,
            text="Lukk",
            width=90,
            command=self.destroy,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=2)

        self._refresh_rows()

    def _reset_filters(self) -> None:
        self.status_var.set("Alle")
        self.search_entry.delete(0, "end")
        self._refresh_rows()

    def _filtered_rows(self) -> list[dict]:
        status = "" if self.status_var.get() == "Alle" else self.status_var.get()
        return filter_rows(
            self.model.get("jobs") or [],
            status=status,
            search=self.search_entry.get(),
        )

    def _refresh_rows(self) -> None:
        for child in self.rows_frame.winfo_children():
            child.destroy()

        headers = (
            "Jobb", "Navn", "Status", "Arkivdeler", "Tester OK/feil",
            "Mismatch", "Vurderingssaker", "Funn", "Depotvurdering", "Handling",
        )
        for col, label in enumerate(headers):
            ctk.CTkLabel(
                self.rows_frame,
                text=label,
                anchor="w",
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=0, column=col, sticky="ew", padx=6, pady=(4, 8))

        rows = self._filtered_rows()
        for index, row in enumerate(rows, start=1):
            report_json = Path(row["report_json"]) if row.get("report_json") else None
            assessment = _live_assessment_label(report_json)
            values = (
                row.get("job_id"),
                row.get("name"),
                row.get("control_status"),
                row.get("archive_part_count"),
                f"{row.get('tests_ok', 0)} / {row.get('tests_error', 0)}",
                row.get("reconciliation_mismatch", 0),
                row.get("review_cases", row.get("review_points", 0)),
                row.get("review_findings", row.get("review_points", 0)),
                assessment,
            )
            for col, value in enumerate(values):
                ctk.CTkLabel(
                    self.rows_frame,
                    text=_display(value),
                    anchor="w",
                    justify="left",
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=index * 2 - 1, column=col, sticky="ew", padx=6, pady=(4, 2))

            ctk.CTkButton(
                self.rows_frame,
                text="Vurder",
                width=78,
                state="normal" if report_json and report_json.is_file() else "disabled",
                command=lambda p=report_json: self._open_assessment(p),
                fg_color=theme.BUTTON_BG,
                hover_color=theme.BUTTON_HOVER,
            ).grid(row=index * 2 - 1, column=9, padx=6, pady=(4, 2))

            detail = (
                f"Kilde: {_display(row.get('source_extraction'))}   |   "
                f"Mapper: {_display(row.get('folder_count'))}   |   "
                f"Registreringer: {_display(row.get('registration_count'))}   |   "
                f"Dokumentobjekter: {_display(row.get('document_object_count'))}\n"
                f"{_display(row.get('control_message'))}"
            )
            ctk.CTkLabel(
                self.rows_frame,
                text=detail,
                anchor="w",
                justify="left",
                wraplength=1420,
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(
                row=index * 2,
                column=0,
                columnspan=10,
                sticky="ew",
                padx=6,
                pady=(0, 10),
            )

        self.count_var.set(
            f"Viser {len(rows)} av {len(self.model.get('jobs') or [])} jobb(er)"
        )

    def _open_assessment(self, report_path: Path | None) -> None:
        if report_path is None or not report_path.is_file():
            messagebox.showwarning(
                APP_NAME,
                "Depotrapporten finnes ikke lenger på forventet sted.",
                parent=self,
            )
            return

        existing = self._assessment_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.destroy()
            except Exception:
                pass

        dialog = DirectDepotAssessmentDialogA12(
            self,
            report_path=report_path,
            user_identity=self.user_identity,
        )
        self._assessment_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._assessment_closed(event, d),
            add="+",
        )

    def _assessment_closed(self, event, dialog) -> None:
        if event.widget is dialog and self._assessment_dialog is dialog:
            self._assessment_dialog = None
            # Re-read the assessment sidecar so status changes become visible
            # immediately in the worklist.
            self.after_idle(self._refresh_rows)

    def _open_batch_html(self) -> None:
        if self.overview_html is None or not self.overview_html.is_file():
            return
        import webbrowser
        webbrowser.open(self.overview_html.resolve().as_uri())
