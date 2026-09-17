from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from noark5_workflow.analysis.depot_annotations import (
    ANNOTATION_STATUSES,
    ANNOTATION_TYPES,
    list_depot_annotations,
    record_depot_annotation,
)
from noark5_workflow.core.identity import UserIdentity
from noark5_workflow.external_evidence.arkade5 import (
    Arkade5ImportError,
    import_arkade5_report,
    infer_work_operations_from_depot_report,
    list_arkade5_imports,
    load_arkade5_import,
)
from version import APP_NAME
from . import theme


TOTAL_FIELDS = (
    ("archive_count", "Arkiv"),
    ("archive_creator_count", "Arkivskapere"),
    ("archive_part_count", "Arkivdeler"),
    ("classification_system_count", "Klassifikasjonssystem"),
    ("class_count", "Klasser"),
    ("folder_count", "Mapper"),
    ("registration_count", "Registreringer"),
    ("journalpost_count", "Journalposter"),
    ("document_description_count", "Dokumentbeskrivelser"),
    ("document_object_count", "Dokumentobjekter"),
)

ARCHIVE_PART_FIELDS = (
    ("folder_count", "Mapper"),
    ("registration_count", "Registreringer"),
    ("journalpost_count", "Journalposter"),
    ("document_description_count", "Dokumentbeskrivelser"),
    ("document_object_count", "Dokumentobjekter"),
    ("screening_count", "Skjerminger"),
    ("disposal_decision_count", "Kassasjonsvedtak"),
    ("performed_disposal_count", "Utført kassasjon"),
    ("deletion_count", "Slettinger"),
)

ANNOTATION_LABELS = {
    "note": "Merknad",
    "deviation": "Avvik",
    "question": "Spørsmål",
    "follow_up": "Oppfølging",
    "accepted_deviation": "Akseptert avvik",
}
LABEL_TO_ANNOTATION = {label: value for value, label in ANNOTATION_LABELS.items()}

STATUS_LABELS = {
    "active": "Aktiv",
    "resolved": "Avklart",
    "closed": "Lukket",
}
LABEL_TO_STATUS = {label: value for value, label in STATUS_LABELS.items()}

VIEW_LABELS = {
    "total": "Totalt",
    "technical": "Teknisk",
    "archive_parts": "Arkivdeler",
    "review_points": "Vurderingspunkter",
}


def _display(value) -> str:
    return "–" if value is None else str(value)


def total_view_text(model: dict) -> str:
    summary = model.get("summary") or {}
    lines = ["TOTALOVERSIKT FOR UTTREKKET", ""]
    for key, label in TOTAL_FIELDS:
        lines.append(f"{label}: {_display(summary.get(key))}")

    evidence = model.get("evidence") or {}
    source_profile = evidence.get("source_presentation_profile")
    source_file = evidence.get("source_presentation_file")
    if source_profile or source_file:
        lines.extend(["", "SPORBARHET"])
        if source_profile:
            lines.append(f"Presentasjonsprofil: {source_profile}")
        if source_file:
            lines.append(f"Kildepresentasjon: {source_file}")
    return "\n".join(lines)


def technical_view_text(model: dict) -> str:
    technical = model.get("technical_validation") or {}
    summary = technical.get("summary") or {}
    reconciliation = technical.get("reconciliation") or {}
    lines = [
        "TEKNISK VALIDERING", "",
        f"Status: {_display(technical.get('status'))}",
        ("Tester: " f"OK {summary.get('ok', 0)}, " f"feil {summary.get('error', 0)}, "
         f"legacy-deaktivert {summary.get('legacy_disabled', 0)}, " f"annet {summary.get('other', 0)}"),
        ("Reconciliation: " f"match {reconciliation.get('match', 0)}, "
         f"mismatch {reconciliation.get('mismatch', 0)}, "
         f"ikke sammenlignbar {reconciliation.get('not_comparable', 0)}, "
         f"annet {reconciliation.get('other', 0)}"),
        "", "TESTRESULTATER",
    ]
    tests = technical.get("tests") or []
    if not tests:
        lines.append("Ingen testresultater er materialisert i rapporten.")
    else:
        for item in tests:
            test_id = item.get("test_id") or "ukjent test"
            legacy = item.get("legacy_job_id")
            point = item.get("test_point")
            status = item.get("status") or "ukjent"
            suffix = [str(v) for v in (legacy, point) if v]
            context = f" ({' – '.join(suffix)})" if suffix else ""
            lines.append(f"• {test_id}{context}: {status}")
    return "\n".join(lines)


def review_points_view_text(model: dict) -> str:
    deviations = model.get("deviations") or []
    standard = (model.get("standard_values") or {}).get("summary") or {}
    counts = standard.get("status_counts") or {}
    lines = ["VURDERINGSPUNKTER", ""]
    if deviations:
        for item in deviations:
            severity = str(item.get("severity") or "").strip()
            summary = str(item.get("summary") or item.get("category") or "Uspesifisert")
            prefix = f"[{severity}] " if severity else ""
            lines.append(f"• {prefix}{summary}")
            note = str(item.get("note") or "").strip()
            if note:
                lines.append(f"  {note}")
    else:
        lines.append("Ingen automatiske vurderingspunkter er materialisert.")
    lines.extend([
        "", "STANDARDVERDIER",
        f"Tester med kontroller: {standard.get('tests_with_checks', 0)}",
        f"Alle observerte verdier standard: {counts.get('all_observed_values_standard', 0)}",
        f"Tilleggsverdier observert: {counts.get('additional_observed_values', 0)}",
        f"Ingen observerte verdier: {counts.get('no_observed_values', 0)}",
        f"Annet: {counts.get('other', 0)}",
    ])
    return "\n".join(lines)


def archive_part_label(row: dict, index: int) -> str:
    identity = row.get("archive_part") or {}
    system_id = str(identity.get("system_id") or "").strip()
    title = str(identity.get("title") or identity.get("name") or "").strip()
    descriptive = title or system_id or "Uten navn"
    if system_id and title:
        descriptive = f"{title} [{system_id}]"
    return f"{index + 1}. {descriptive}"


def archive_part_target(row: dict, index: int) -> tuple[str, str]:
    identity = row.get("archive_part") or {}
    system_id = str(identity.get("system_id") or "").strip()
    return (system_id or f"archive-part-{index + 1}", archive_part_label(row, index))


def archive_part_view_text(row: dict) -> str:
    identity = row.get("archive_part") or {}
    lines = [
        "ARKIVDEL", "",
        f"System-ID: {_display(identity.get('system_id'))}",
        f"Navn/tittel: {_display(identity.get('title') or identity.get('name'))}",
        "", "NØKKELTALL",
    ]
    for key, label in ARCHIVE_PART_FIELDS:
        lines.append(f"{label}: {_display(row.get(key))}")
    sources = row.get("sources") or {}
    if sources:
        lines.extend(["", "SPORBARHET"])
        for field_id, source in sources.items():
            if not isinstance(source, dict):
                continue
            details = " / ".join(str(v) for v in (source.get("test_id"), source.get("path")) if v)
            if details:
                lines.append(f"{field_id}: {details}")
    return "\n".join(lines)


class DepotAnnotationsDialog(ctk.CTkToplevel):
    """Add structured comments to one view or subview of a depot report."""

    def __init__(
        self,
        master,
        *,
        report_path: Path,
        user_identity: dict[str, str] | None,
        view_id: str,
        target_type: str,
        target_id: str,
        target_label: str,
    ):
        super().__init__(master)
        self.title("Kommentarer – depotresultat")
        self.geometry("760x620")
        self.minsize(660, 520)
        self.transient(master)
        self.report_path = Path(report_path)
        self.user = UserIdentity.from_mapping(user_identity)
        self.view_id = view_id
        self.target_type = target_type
        self.target_id = target_id
        self.target_label = target_label

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text=f"Kommentarer til: {target_label}",
            anchor="w", justify="left", wraplength=700,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))

        self.history = ctk.CTkTextbox(self, wrap="word", font=theme.font(theme.SMALL_SIZE))
        self.history.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 10))
        self.history.configure(state="disabled")

        form = ctk.CTkFrame(self)
        form.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))
        form.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(form, text="Type", anchor="w").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        self.type_var = ctk.StringVar(value=ANNOTATION_LABELS["note"])
        ctk.CTkOptionMenu(
            form,
            variable=self.type_var,
            values=[ANNOTATION_LABELS[t] for t in ANNOTATION_TYPES],
        ).grid(row=0, column=1, sticky="ew", padx=(6, 10), pady=(10, 6))
        ctk.CTkLabel(form, text="Kommentar", anchor="nw").grid(row=1, column=0, sticky="nw", padx=10, pady=(6, 10))
        self.text = ctk.CTkTextbox(form, height=120, wrap="word")
        self.text.grid(row=1, column=1, sticky="ew", padx=(6, 10), pady=(6, 10))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)
        self.save_button = ctk.CTkButton(bottom, text="Lagre kommentar", command=self._save, width=130)
        self.save_button.grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(
            bottom, text="Lukk", command=self.destroy, width=90,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=2, padx=(8, 0))
        if self.user is None:
            self.save_button.configure(state="disabled")
        self._refresh()

    def _refresh(self) -> None:
        try:
            items = list_depot_annotations(
                self.report_path,
                view_id=self.view_id,
                target_type=self.target_type,
                target_id=self.target_id,
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        lines = []
        for item in items:
            user = item.get("user") or {}
            kind = ANNOTATION_LABELS.get(item.get("annotation_type"), item.get("annotation_type", ""))
            who = user.get("username") or user.get("user_id") or "ukjent"
            lines.extend([
                f"[{kind}] {item.get('created_at', '')} – {who}",
                str(item.get("text") or ""),
                "",
            ])
        if not lines:
            lines = ["Ingen kommentarer er registrert for denne visningen."]
        self.history.configure(state="normal")
        self.history.delete("1.0", "end")
        self.history.insert("1.0", "\n".join(lines).rstrip())
        self.history.configure(state="disabled")

    def _save(self) -> None:
        if self.user is None:
            messagebox.showerror(APP_NAME, "Kommentar krever aktiv brukerprofil.", parent=self)
            return
        annotation_type = LABEL_TO_ANNOTATION.get(self.type_var.get())
        text = self.text.get("1.0", "end").strip()
        try:
            record_depot_annotation(
                self.report_path,
                annotation_type=annotation_type or "",
                text=text,
                user=self.user,
                view_id=self.view_id,
                target_type=self.target_type,
                target_id=self.target_id,
                target_label=self.target_label,
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        self.text.delete("1.0", "end")
        self._refresh()


class DepotAnnotationOverviewDialog(ctk.CTkToplevel):
    """Combined annotation worklist with filters over one depot report."""

    ALL = "Alle"

    def __init__(self, master, *, report_path: Path):
        super().__init__(master)
        self.title("Alle kommentarer – depotresultat")
        self.geometry("1060x760")
        self.minsize(880, 620)
        self.transient(master)
        self.report_path = Path(report_path)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        try:
            self._all_items = list_depot_annotations(self.report_path)
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            self._all_items = []

        ctk.CTkLabel(
            self,
            text=("Samlet arbeidsliste for kommentarer til denne rapportinstansen. "
                  "Filtrene bruker samme annotasjonsmodell som senere kan eksponeres i CLI."),
            anchor="w", justify="left", wraplength=1000,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))

        filters = ctk.CTkFrame(self)
        filters.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))
        for col in range(6):
            filters.grid_columnconfigure(col, weight=1 if col in (0, 1, 2, 3, 4) else 0)

        self.type_var = ctk.StringVar(value=self.ALL)
        self.status_var = ctk.StringVar(value=self.ALL)
        self.view_var = ctk.StringVar(value=self.ALL)
        self.target_var = ctk.StringVar(value=self.ALL)
        self.user_var = ctk.StringVar(value=self.ALL)

        type_values = [self.ALL] + [ANNOTATION_LABELS[t] for t in ANNOTATION_TYPES]
        status_values = [self.ALL] + [STATUS_LABELS[s] for s in ANNOTATION_STATUSES]
        view_ids = sorted({(item.get("target") or {}).get("view_id") for item in self._all_items if (item.get("target") or {}).get("view_id")})
        self._view_lookup = {VIEW_LABELS.get(view, view): view for view in view_ids}
        view_values = [self.ALL] + list(self._view_lookup)

        target_pairs = []
        for item in self._all_items:
            target = item.get("target") or {}
            target_id = str(target.get("target_id") or "").strip()
            target_label = str(target.get("target_label") or target_id).strip()
            if target_id and target_label:
                target_pairs.append((target_label, target_id))
        self._target_lookup = {}
        for label, target_id in target_pairs:
            display = label if label not in self._target_lookup else f"{label} [{target_id}]"
            self._target_lookup[display] = target_id
        target_values = [self.ALL] + list(self._target_lookup)

        usernames = sorted({
            str((item.get("user") or {}).get("username") or (item.get("user") or {}).get("user_id") or "").strip()
            for item in self._all_items
            if ((item.get("user") or {}).get("username") or (item.get("user") or {}).get("user_id"))
        })
        user_values = [self.ALL] + usernames

        self._filter_control(filters, 0, "Type", self.type_var, type_values)
        self._filter_control(filters, 1, "Status", self.status_var, status_values)
        self._filter_control(filters, 2, "Visning", self.view_var, view_values)
        self._filter_control(filters, 3, "Del / mål", self.target_var, target_values)
        self._filter_control(filters, 4, "Bruker", self.user_var, user_values)

        search_frame = ctk.CTkFrame(filters, fg_color="transparent")
        search_frame.grid(row=2, column=0, columnspan=5, sticky="ew", padx=8, pady=(4, 8))
        search_frame.grid_columnconfigure(0, weight=1)
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Søk i kommentar, delnavn eller mål-ID")
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.search_entry.bind("<Return>", lambda _event: self._refresh())
        ctk.CTkButton(search_frame, text="Filtrer", width=90, command=self._refresh).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(
            search_frame, text="Nullstill", width=90, command=self._reset_filters,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=2)

        self.results = ctk.CTkTextbox(self, wrap="word", font=theme.font(theme.SMALL_SIZE))
        self.results.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 10))
        self.results.configure(state="disabled")

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)
        self.count_var = ctk.StringVar(value="")
        ctk.CTkLabel(bottom, textvariable=self.count_var, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            bottom, text="Lukk", width=90, command=self.destroy,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)
        self._refresh()

    def _filter_control(self, parent, column: int, label: str, variable, values: list[str]) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=column, rowspan=2, sticky="ew", padx=8, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=label, anchor="w").grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkOptionMenu(frame, variable=variable, values=values, command=lambda _value: self._refresh()).grid(
            row=1, column=0, sticky="ew"
        )

    def _selected(self, value: str) -> str | None:
        return None if value == self.ALL else value

    def _refresh(self) -> None:
        type_label = self._selected(self.type_var.get())
        status_label = self._selected(self.status_var.get())
        view_label = self._selected(self.view_var.get())
        target_label = self._selected(self.target_var.get())
        username = self._selected(self.user_var.get())
        try:
            items = list_depot_annotations(
                self.report_path,
                annotation_type=LABEL_TO_ANNOTATION.get(type_label) if type_label else None,
                status=LABEL_TO_STATUS.get(status_label) if status_label else None,
                view_id=self._view_lookup.get(view_label) if view_label else None,
                target_id=self._target_lookup.get(target_label) if target_label else None,
                username=username,
                text_search=self.search_entry.get(),
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        lines = []
        for item in items:
            target = item.get("target") or {}
            user = item.get("user") or {}
            kind = ANNOTATION_LABELS.get(item.get("annotation_type"), item.get("annotation_type", ""))
            status = STATUS_LABELS.get(item.get("status"), item.get("status", ""))
            view = VIEW_LABELS.get(target.get("view_id"), target.get("view_id") or "Ukjent visning")
            target_name = target.get("target_label") or target.get("target_id") or view
            who = user.get("username") or user.get("user_id") or "ukjent"
            lines.extend([
                f"[{kind}] [{status}] {view} → {target_name}",
                f"{item.get('created_at', '')} – {who}",
                str(item.get("text") or ""),
                "",
            ])
        if not lines:
            lines = ["Ingen kommentarer samsvarer med valgte filtre."]
        self.results.configure(state="normal")
        self.results.delete("1.0", "end")
        self.results.insert("1.0", "\n".join(lines).rstrip())
        self.results.configure(state="disabled")
        self.count_var.set(f"Viser {len(items)} av {len(self._all_items)} kommentar(er)")

    def _reset_filters(self) -> None:
        self.type_var.set(self.ALL)
        self.status_var.set(self.ALL)
        self.view_var.set(self.ALL)
        self.target_var.set(self.ALL)
        self.user_var.set(self.ALL)
        self.search_entry.delete(0, "end")
        self._refresh()


def arkade_evidence_text(report_path: Path | None) -> str:
    if report_path is None:
        return "Ingen depotrapport er valgt; ekstern evidens kan derfor ikke knyttes til aktivt datagrunnlag."
    try:
        work_operations = infer_work_operations_from_depot_report(report_path)
        imports = list_arkade5_imports(work_operations)
    except Exception as exc:
        return f"Kunne ikke lese ekstern evidens: {exc}"
    if not imports:
        return (
            "ARKADE 5 – EKSTERN EVIDENS\n\n"
            "Ingen Arkade 5-rapporter er importert for dette arbeidsområdet.\n"
            "Importer en JSON-testrapport for å bevare originalen, normalisere testresultatene "
            "og sammenligne sikre målepunkter mot N5WF-depotrapporten."
        )
    lines = ["ARKADE 5 – EKSTERN EVIDENS", "", f"Importer: {len(imports)}", ""]
    for manifest in imports:
        source = manifest.get("source") or {}
        summary = manifest.get("source_summary") or {}
        rec = manifest.get("reconciliation_summary") or {}
        lines.extend([
            f"Import: {manifest.get('import_id', '')}",
            f"Kilde: {source.get('original_name', '')}",
            f"Arkade testdato: {summary.get('date_of_testing') or '–'}",
            f"Tester: {summary.get('number_of_tests_run') or '–'} | "
            f"Errors: {summary.get('number_of_errors') or 0} | "
            f"Warnings: {summary.get('number_of_warnings') or 0}",
            f"Reconciliation: match {rec.get('match', 0)}, "
            f"mismatch {rec.get('mismatch', 0)}, "
            f"ikke tilgjengelig {rec.get('not_available', 0)}",
            f"SHA-256: {source.get('sha256', '')}",
            "",
        ])
    return "\n".join(lines).rstrip()


class DepotResultViewsDialog(ctk.CTkToplevel):
    """Specialized read-only views with structured annotations."""

    def __init__(
        self,
        master,
        *,
        model: dict,
        report_path: str | Path | None = None,
        user_identity: dict[str, str] | None = None,
    ):
        super().__init__(master)
        self.title("Resultatvisninger – Noark 5")
        self.geometry("980x760")
        self.minsize(820, 620)
        self.transient(master)
        self.model = model
        self.report_path = Path(report_path) if report_path else None
        self.user_identity = user_identity
        self._annotation_dialog = None
        self._annotation_overview_dialog = None
        self._external_evidence_import = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text="Visningene leser den allerede genererte depotrapporten og kjører ingen ny analyse.",
            anchor="w", justify="left", font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))

        tabs = ctk.CTkTabview(self)
        tabs.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 10))
        for name in ("Totalt", "Teknisk", "Arkivdeler", "Vurderingspunkter", "Ekstern evidens"):
            tabs.add(name)

        self._fill_text_tab(tabs.tab("Totalt"), total_view_text(model), "total", "Totaloversikt")
        self._fill_text_tab(tabs.tab("Teknisk"), technical_view_text(model), "technical", "Teknisk validering")
        self._fill_text_tab(
            tabs.tab("Vurderingspunkter"), review_points_view_text(model),
            "review_points", "Vurderingspunkter",
        )
        self._build_archive_parts_tab(tabs.tab("Arkivdeler"))
        self._build_external_evidence_tab(tabs.tab("Ekstern evidens"))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            bottom, text="Alle kommentarer...", width=150,
            state="normal" if self.report_path else "disabled",
            command=self._open_annotation_overview,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(
            bottom, text="Lukk", width=90, fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER, command=self.destroy,
        ).grid(row=0, column=2)

    def _build_external_evidence_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self.external_evidence_text = ctk.CTkTextbox(
            tab, wrap="word", font=theme.font(theme.SMALL_SIZE)
        )
        self.external_evidence_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))
        buttons = ctk.CTkFrame(tab, fg_color="transparent")
        buttons.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 8))
        buttons.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            buttons,
            text="Importer Arkade 5 JSON...",
            width=175,
            state="normal" if self.report_path else "disabled",
            command=self._import_arkade5_evidence,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)
        self._refresh_external_evidence()

    def _refresh_external_evidence(self) -> None:
        if not hasattr(self, "external_evidence_text"):
            return
        text = arkade_evidence_text(self.report_path)
        self.external_evidence_text.configure(state="normal")
        self.external_evidence_text.delete("1.0", "end")
        self.external_evidence_text.insert("1.0", text)
        self.external_evidence_text.configure(state="disabled")

    def _import_arkade5_evidence(self) -> None:
        if self.report_path is None:
            return
        filename = filedialog.askopenfilename(
            title="Importer Arkade 5 JSON-testrapport",
            filetypes=[("JSON", "*.json"), ("Alle filer", "*.*")],
            parent=self,
        )
        if not filename:
            return
        try:
            work_operations = infer_work_operations_from_depot_report(self.report_path)
            manifest = import_arkade5_report(
                filename,
                work_operations=work_operations,
                depot_report_path=self.report_path,
                imported_by=self.user_identity,
            )
        except (Arkade5ImportError, OSError, ValueError) as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        self._external_evidence_import = manifest
        self._refresh_external_evidence()
        rec = manifest.get("reconciliation_summary") or {}
        messagebox.showinfo(
            APP_NAME,
            "Arkade 5-rapport importert som ekstern evidens.\n\n"
            f"Match: {rec.get('match', 0)}\n"
            f"Mismatch: {rec.get('mismatch', 0)}\n"
            f"Ikke tilgjengelig: {rec.get('not_available', 0)}",
            parent=self,
        )

    def _open_annotation_overview(self) -> None:
        if self.report_path is None:
            return
        existing = self._annotation_overview_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.focus()
                    existing.lift()
                    return
            except Exception:
                pass
        dialog = DepotAnnotationOverviewDialog(self, report_path=self.report_path)
        self._annotation_overview_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog: self._annotation_overview_closed(event, d),
            add="+",
        )

    def _annotation_overview_closed(self, event, dialog) -> None:
        if event.widget is dialog and self._annotation_overview_dialog is dialog:
            self._annotation_overview_dialog = None

    def _fill_text_tab(self, tab, text: str, view_id: str, label: str) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        box = ctk.CTkTextbox(tab, wrap="word", font=theme.font(theme.SMALL_SIZE))
        box.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))
        box.insert("1.0", text)
        box.configure(state="disabled")
        ctk.CTkButton(
            tab,
            text="Kommentarer...",
            width=120,
            state="normal" if self.report_path else "disabled",
            command=lambda: self._open_annotations(
                view_id=view_id,
                target_type="view",
                target_id=view_id,
                target_label=label,
            ),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=1, column=0, sticky="e", padx=8, pady=(4, 8))

    def _build_archive_parts_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        self._archive_parts = list(self.model.get("archive_parts") or [])
        self._archive_labels = [archive_part_label(row, index) for index, row in enumerate(self._archive_parts)]
        self._archive_index = 0

        if not self._archive_parts:
            self._fill_text_tab(tab, "Ingen arkivdelsresultater er materialisert i rapporten.", "archive_parts", "Arkivdeler")
            return

        self.archive_part_var = ctk.StringVar(value=self._archive_labels[0])
        ctk.CTkOptionMenu(
            tab, variable=self.archive_part_var, values=self._archive_labels,
            command=self._archive_part_selected,
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        self.archive_part_text = ctk.CTkTextbox(tab, wrap="word", font=theme.font(theme.SMALL_SIZE))
        self.archive_part_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 4))
        self.archive_annotation_button = ctk.CTkButton(
            tab, text="Kommentarer til arkivdel...", width=175,
            state="normal" if self.report_path else "disabled",
            command=self._open_archive_part_annotations,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        self.archive_annotation_button.grid(row=2, column=0, sticky="e", padx=8, pady=(4, 8))
        self._show_archive_part(0)

    def _archive_part_selected(self, label: str) -> None:
        try:
            index = self._archive_labels.index(label)
        except ValueError:
            return
        self._show_archive_part(index)

    def _show_archive_part(self, index: int) -> None:
        if not self._archive_parts:
            return
        self._archive_index = index
        self.archive_part_text.configure(state="normal")
        self.archive_part_text.delete("1.0", "end")
        self.archive_part_text.insert("1.0", archive_part_view_text(self._archive_parts[index]))
        self.archive_part_text.configure(state="disabled")

    def _open_archive_part_annotations(self) -> None:
        if not self._archive_parts:
            return
        target_id, target_label = archive_part_target(self._archive_parts[self._archive_index], self._archive_index)
        self._open_annotations(
            view_id="archive_parts",
            target_type="archive_part",
            target_id=target_id,
            target_label=target_label,
        )

    def _open_annotations(self, *, view_id: str, target_type: str, target_id: str, target_label: str) -> None:
        if self.report_path is None:
            return
        existing = self._annotation_dialog
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.destroy()
            except Exception:
                pass
        dialog = DepotAnnotationsDialog(
            self,
            report_path=self.report_path,
            user_identity=self.user_identity,
            view_id=view_id,
            target_type=target_type,
            target_id=target_id,
            target_label=target_label,
        )
        self._annotation_dialog = dialog
