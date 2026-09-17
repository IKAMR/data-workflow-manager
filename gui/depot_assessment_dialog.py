from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from noark5_workflow.analysis.depot_assessment import (
    ASSESSMENT_STATUSES,
    load_depot_assessment,
    record_depot_assessment,
)
from noark5_workflow.core.identity import UserIdentity
from version import APP_NAME
from . import theme
from .depot_result_views import DepotResultViewsDialog


STATUS_LABELS = {
    "accepted": "Akseptert",
    "accepted_with_deviation": "Akseptert med avvik",
    "requires_clarification": "Krever avklaring",
    "new_extraction_required": "Nytt uttrekk kreves",
}
LABEL_TO_STATUS = {label: status for status, label in STATUS_LABELS.items()}

SUMMARY_LABELS = (
    ("archive_count", "Arkiv"),
    ("archive_creator_count", "Arkivskapere"),
    ("archive_part_count", "Arkivdeler"),
    ("folder_count", "Mapper"),
    ("registration_count", "Registreringer"),
    ("journalpost_count", "Journalposter"),
    ("document_description_count", "Dokumentbeskrivelser"),
    ("document_object_count", "Dokumentobjekter"),
)


def latest_depot_report(work_operations: str | Path | None) -> Path | None:
    """Return latest depot report for one job's work-operations area."""
    if not work_operations:
        return None
    root = Path(work_operations) / "noark5_reports" / "depot_validation"
    if not root.is_dir():
        return None
    candidates = [
        run / "depot_validation_report.json"
        for run in root.iterdir()
        if run.is_dir() and (run / "depot_validation_report.json").is_file()
    ]
    return max(candidates, key=lambda p: p.parent.name) if candidates else None


def report_summary_text(model: dict) -> str:
    """Build a compact, review-oriented summary without re-analysing the report."""
    summary = model.get("summary") or {}
    technical = model.get("technical_validation") or {}
    tech_counts = technical.get("summary") or {}
    reconciliation = technical.get("reconciliation") or {}
    deviations = model.get("deviations") or []

    lines = ["SAMMENDRAG"]
    count_parts = []
    for key, label in SUMMARY_LABELS:
        value = summary.get(key)
        if value is not None:
            count_parts.append(f"{label}: {value}")
    if count_parts:
        lines.append(" • ".join(count_parts))

    lines.extend([
        "",
        "TEKNISK VALIDERING",
        f"Status: {technical.get('status', 'ukjent')}",
        (
            "Tester: "
            f"OK {tech_counts.get('ok', 0)}, "
            f"feil {tech_counts.get('error', 0)}, "
            f"legacy-deaktivert {tech_counts.get('legacy_disabled', 0)}, "
            f"annet {tech_counts.get('other', 0)}"
        ),
        (
            "Reconciliation: "
            f"match {reconciliation.get('match', 0)}, "
            f"mismatch {reconciliation.get('mismatch', 0)}, "
            f"ikke sammenlignbar {reconciliation.get('not_comparable', 0)}, "
            f"annet {reconciliation.get('other', 0)}"
        ),
        "",
        "VURDERINGSPUNKTER",
    ])

    if deviations:
        for item in deviations:
            text = str(item.get("summary") or item.get("category") or "Uspesifisert vurderingspunkt")
            severity = str(item.get("severity") or "").strip()
            prefix = f"[{severity}] " if severity else ""
            lines.append(f"• {prefix}{text}")
            note = str(item.get("note") or "").strip()
            if note:
                lines.append(f"  {note}")
    else:
        lines.append("Ingen automatiske vurderingspunkter identifisert.")

    lines.extend([
        "",
        "Rapporten gjør ingen automatisk faglig godkjenning. Depotets vurdering registreres nedenfor.",
    ])
    return "\n".join(lines)


class DepotAssessmentDialog(ctk.CTkToplevel):
    """Review one concrete depot report and register the human depot assessment."""

    def __init__(
        self,
        master,
        *,
        user_identity: dict[str, str] | None = None,
        work_operations: str | Path | None = None,
    ):
        super().__init__(master)
        self.title("Depotvurdering – Noark 5")
        self.geometry("900x780")
        self.minsize(780, 680)
        self.transient(master)

        self.user = UserIdentity.from_mapping(user_identity)
        self.work_operations = Path(work_operations) if work_operations else None
        self.report_path: Path | None = None
        self.report_model: dict | None = None
        self._result_views_dialog = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        intro = ctk.CTkLabel(
            self,
            text=(
                "Les rapportens sammendrag og registrer depotets faglige vurdering. "
                "Originalrapporten endres ikke."
            ),
            justify="left",
            anchor="w",
            wraplength=840,
            font=theme.font(theme.NORMAL_SIZE),
        )
        intro.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))

        report_frame = ctk.CTkFrame(self)
        report_frame.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))
        report_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            report_frame,
            text="Velg rapport",
            width=110,
            command=self._choose_report,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, padx=(10, 8), pady=10)

        self.report_var = ctk.StringVar(value="Ingen rapport valgt")
        ctk.CTkLabel(
            report_frame,
            textvariable=self.report_var,
            anchor="w",
            justify="left",
            wraplength=600,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=10)

        self.result_views_button = ctk.CTkButton(
            report_frame,
            text="Resultatvisninger",
            width=130,
            state="disabled",
            command=self._open_result_views,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self.result_views_button.grid(row=0, column=2, padx=(0, 6), pady=10)

        self.open_report_button = ctk.CTkButton(
            report_frame,
            text="Åpne full rapport",
            width=130,
            state="disabled",
            command=self._open_full_report,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self.open_report_button.grid(row=0, column=3, padx=(0, 10), pady=10)

        current_frame = ctk.CTkFrame(self)
        current_frame.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))
        current_frame.grid_columnconfigure(0, weight=1)
        self.current_var = ctk.StringVar(value="Ingen lagret vurdering lastet.")
        ctk.CTkLabel(
            current_frame,
            textvariable=self.current_var,
            anchor="w",
            justify="left",
            wraplength=840,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        report_content = ctk.CTkFrame(self)
        report_content.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 10))
        report_content.grid_columnconfigure(0, weight=1)
        report_content.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            report_content,
            text="RAPPORTINNHOLD",
            anchor="w",
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.TEXT_MUTED,
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        self.report_text = ctk.CTkTextbox(
            report_content,
            wrap="word",
            height=210,
            font=theme.font(theme.SMALL_SIZE),
            state="disabled",
        )
        self.report_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._set_report_text("Ingen depotvalideringsrapport lastet.")

        form = ctk.CTkFrame(self)
        form.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 10))
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="Status", anchor="w").grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 6)
        )
        self.status_var = ctk.StringVar(value=STATUS_LABELS["requires_clarification"])
        self.status_menu = ctk.CTkOptionMenu(
            form,
            variable=self.status_var,
            values=[STATUS_LABELS[s] for s in ASSESSMENT_STATUSES],
        )
        self.status_menu.grid(row=0, column=1, sticky="ew", padx=(6, 10), pady=(10, 6))

        ctk.CTkLabel(form, text="Bruker", anchor="w").grid(
            row=1, column=0, sticky="w", padx=10, pady=6
        )
        username = self.user.username if self.user else "Ingen aktiv brukerprofil"
        self.user_var = ctk.StringVar(value=username)
        ctk.CTkLabel(form, textvariable=self.user_var, anchor="w").grid(
            row=1, column=1, sticky="ew", padx=(6, 10), pady=6
        )

        ctk.CTkLabel(form, text="Begrunnelse", anchor="nw").grid(
            row=2, column=0, sticky="nw", padx=10, pady=(6, 10)
        )
        self.reason_text = ctk.CTkTextbox(form, height=110, wrap="word")
        self.reason_text.grid(row=2, column=1, sticky="ew", padx=(6, 10), pady=(6, 10))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)

        self.save_button = ctk.CTkButton(
            bottom,
            text="Lagre vurdering",
            width=130,
            command=self._save,
        )
        self.save_button.grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(
            bottom,
            text="Lukk",
            width=90,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self.destroy,
        ).grid(row=0, column=2, padx=(8, 0))

        if self.user is None:
            self.save_button.configure(state="disabled")
            self.current_var.set(
                "Ingen aktiv brukerprofil. Opprett/velg brukerprofil før depotvurdering kan lagres."
            )

        auto_report = latest_depot_report(self.work_operations)
        if auto_report is not None:
            self._load_report(auto_report)
        elif self.work_operations is not None:
            self.report_var.set("Ingen depotvalideringsrapport funnet for aktiv jobb")

    def _set_report_text(self, text: str) -> None:
        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", text)
        self.report_text.configure(state="disabled")

    def _choose_report(self) -> None:
        initialdir = str(self.work_operations) if self.work_operations else None
        filename = filedialog.askopenfilename(
            parent=self,
            title="Velg depotvalideringsrapport",
            initialdir=initialdir,
            filetypes=[
                ("Depotvalideringsrapport", "depot_validation_report.json"),
                ("JSON-filer", "*.json"),
                ("Alle filer", "*.*"),
            ],
        )
        if not filename:
            return
        self._load_report(Path(filename))

    def _load_report(self, path: Path) -> None:
        try:
            model = json.loads(path.read_text(encoding="utf-8"))
            stored = load_depot_assessment(path)
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        if model.get("report_type") != "noark5_depot_validation":
            messagebox.showerror(
                APP_NAME,
                "Valgt fil er ikke en Noark 5 depotvalideringsrapport.",
                parent=self,
            )
            return

        self.report_path = path
        self.report_model = model
        self.report_var.set(str(path))
        self._set_report_text(report_summary_text(model))
        self.result_views_button.configure(state="normal")

        html_path = path.with_suffix(".html")
        self.open_report_button.configure(state="normal" if html_path.is_file() else "disabled")

        if not stored or not stored.get("current"):
            self.current_var.set("Ingen tidligere depotvurdering er registrert for denne rapporten.")
            self.reason_text.delete("1.0", "end")
            return

        current = stored["current"]
        status = str(current.get("status", ""))
        label = STATUS_LABELS.get(status, status or "Ukjent")
        assessed_at = current.get("assessed_at", "")
        user = current.get("user") or {}
        username = user.get("username") or user.get("user_id") or "ukjent bruker"
        reason = current.get("reason", "")
        history_count = len(stored.get("history", []))
        self.current_var.set(
            f"Gjeldende vurdering: {label} – {username} – {assessed_at}\n"
            f"Begrunnelse: {reason}\nHistorikk: {history_count} vurdering(er)."
        )
        if status in STATUS_LABELS:
            self.status_var.set(STATUS_LABELS[status])
        self.reason_text.delete("1.0", "end")
        self.reason_text.insert("1.0", str(reason))

    def _open_result_views(self) -> None:
        if self.report_model is None:
            messagebox.showinfo(APP_NAME, "Velg eller last en depotvalideringsrapport først.", parent=self)
            return
        existing = self._result_views_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.focus()
                    existing.lift()
                    return
            except Exception:
                pass
        dialog = DepotResultViewsDialog(
            self,
            model=self.report_model,
            report_path=self.report_path,
            user_identity=self.user.as_dict() if self.user else None,
        )
        self._result_views_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._result_views_closed(event, d),
            add="+",
        )

    def _result_views_closed(self, event, dialog) -> None:
        if event.widget is dialog and self._result_views_dialog is dialog:
            self._result_views_dialog = None

    def _open_full_report(self) -> None:
        if self.report_path is None:
            return
        html_path = self.report_path.with_suffix(".html")
        if not html_path.is_file():
            messagebox.showinfo(APP_NAME, "HTML-rapporten finnes ikke ved siden av JSON-rapporten.", parent=self)
            return
        try:
            webbrowser.open(html_path.resolve().as_uri())
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Kunne ikke åpne rapporten: {exc}", parent=self)

    def _save(self) -> None:
        if self.report_path is None:
            messagebox.showinfo(APP_NAME, "Velg en depotvalideringsrapport først.", parent=self)
            return
        if self.user is None:
            messagebox.showerror(APP_NAME, "Depotvurdering krever aktiv brukerprofil.", parent=self)
            return

        status = LABEL_TO_STATUS.get(self.status_var.get())
        reason = self.reason_text.get("1.0", "end").strip()
        if not status:
            messagebox.showerror(APP_NAME, "Velg en gyldig vurderingsstatus.", parent=self)
            return
        if not reason:
            messagebox.showerror(APP_NAME, "Skriv en faglig begrunnelse.", parent=self)
            return

        try:
            result = record_depot_assessment(
                self.report_path,
                status=status,
                reason=reason,
                user=self.user,
                render_html=True,
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        messagebox.showinfo(
            APP_NAME,
            "Depotvurderingen er lagret.\n\n"
            f"Historikk: {result['history_count']} vurdering(er).\n"
            "Vurderingsfil og vurdert rapport er skrevet ved siden av originalrapporten.",
            parent=self,
        )
        self._load_report(self.report_path)
