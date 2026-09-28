from __future__ import annotations

import json
from pathlib import Path

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_25 import DepotResultCenterDialogA16_25


class DepotResultCenterDialogA16_26(DepotResultCenterDialogA16_25):
    """a16.26: structured control surface using the same Noark 5 hierarchy as Sammendrag."""

    _CONTROL_FILES = {
        "folders": ("kdrs_c13.json", "kdrs.c13"),
        "registrations": ("kdrs_c14.json", "kdrs.c14"),
        "journalposts": ("kdrs_c15.json", "kdrs.c15"),
        "descriptions": ("kdrs_c21.json", "kdrs.c21"),
        "objects": ("kdrs_c24.json", "kdrs.c24"),
    }

    def __init__(self, master, **kwargs) -> None:
        self._a1625_results_loaded = False
        self._a1625_results: dict[str, dict] = {}
        self._a1625_control_body = None
        self._a10_controls = None
        super().__init__(master, **kwargs)

        # Rebuild the controls page after the complete inheritance chain has
        # finished. This makes a16.26 independent of the older constructor
        # order that could leave the a16.24 text view visible.
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is not None:
            try:
                control_tab = tabs.tab("Kontroller")
                for child in control_tab.winfo_children():
                    child.destroy()
                self._a1625_control_body = None
                self._a10_controls = None
                self._build_controls_tab(control_tab)
            except Exception:
                pass
        if getattr(self, "_archive_parts", None):
            self._render_structured_controls(getattr(self, "_archive_index", 0))

    # ------------------------------------------------------------------
    # Controls UI
    # ------------------------------------------------------------------
    def _build_controls_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            tab,
            text="Kontroller for valgt arkivdel",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        self._a1625_control_body = ctk.CTkScrollableFrame(tab)
        self._a1625_control_body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._a1625_control_body.grid_columnconfigure(0, weight=1)

        # Hidden legacy sink. Do not grid/place it: inherited code may write
        # to it, but the user only sees the structured surface below.
        self._a10_controls = ctk.CTkTextbox(tab, width=1, height=1)

    def _clear_control_body(self) -> None:
        body = self._a1625_control_body
        if body is None:
            return
        for child in body.winfo_children():
            child.destroy()

    def _section(self, parent, row: int, title: str, subtitle: str = ""):
        box = ctk.CTkFrame(parent)
        box.grid(row=row, column=0, sticky="ew", padx=2, pady=(3, 7))
        box.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            box,
            text=title,
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, columnspan=4, sticky="ew", padx=10, pady=(8, 1))
        if subtitle:
            ctk.CTkLabel(
                box,
                text=subtitle,
                anchor="w",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 6))
            header_row = 2
        else:
            header_row = 1

        headers = ("Kontroll", "Resultat / verdi", "Kilde", "Status")
        widths = (210, 520, 100, 70)
        for col, (label, width) in enumerate(zip(headers, widths)):
            box.grid_columnconfigure(col, weight=1 if col == 1 else 0)
            ctk.CTkLabel(
                box,
                text=label,
                width=width,
                anchor="w",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=header_row, column=col, sticky="ew", padx=(10 if col == 0 else 4, 4), pady=(2, 4))
        return box, header_row + 1

    def _control_row(self, box, row: int, label: str, value: str, source: str, status: str = "OK") -> int:
        text_color = theme.TEXT_SUB
        for col, text in enumerate((label, value, source, status)):
            ctk.CTkLabel(
                box,
                text=text,
                anchor="w",
                justify="left",
                wraplength=620 if col == 1 else 240,
                text_color=text_color,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=row, column=col, sticky="ew", padx=(10 if col == 0 else 4, 4), pady=2)
        return row + 1

    # ------------------------------------------------------------------
    # Existing XPath result materialization
    # ------------------------------------------------------------------
    def _load_control_results(self) -> None:
        if self._a1625_results_loaded:
            return
        self._a1625_results_loaded = True
        evidence = self.model.get("evidence") or {}
        xpath_run = str(evidence.get("source_xpath_run") or "").strip()
        if not xpath_run:
            return
        base = Path(xpath_run) / "results"
        for key, (filename, _source) in self._CONTROL_FILES.items():
            path = base / filename
            if not path.is_file():
                self._a1625_results[key] = {}
                continue
            try:
                self._a1625_results[key] = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self._a1625_results[key] = {}

    def _values_for_row(self, key: str, row: dict) -> dict:
        self._load_control_results()
        result = self._a1625_results.get(key) or {}
        values = result.get("values") or {}
        if row.get("is_all_archive_parts"):
            return values
        system_id = str((row.get("archive_part") or {}).get("system_id") or "").strip()
        if not system_id:
            return {}
        for item in values.get("_archive_parts") or []:
            identity = item.get("archive_part") or {}
            if str(identity.get("system_id") or "").strip() == system_id:
                return item.get("values") or {}
        return {}

    @staticmethod
    def _counter_text(counter, *, skip: set[str] | None = None, limit: int | None = None) -> str:
        if not isinstance(counter, dict) or not counter:
            return "–"
        skip_cf = {v.casefold() for v in (skip or set())}
        items = []
        for name, count in counter.items():
            if str(name).casefold() in skip_cf:
                continue
            try:
                number = int(count)
            except (TypeError, ValueError):
                continue
            items.append((str(name), number))
        items.sort(key=lambda item: (-item[1], item[0].casefold()))
        if limit is not None and len(items) > limit:
            shown = items[:limit]
            rest = len(items) - limit
        else:
            shown = items
            rest = 0
        text = " · ".join(f"{name}: {number:,}".replace(",", " ") for name, number in shown) or "–"
        if rest:
            text += f" · +{rest} flere"
        return text

    @staticmethod
    def _case_sensitive_format_note(counter) -> str:
        if not isinstance(counter, dict) or not counter:
            return "–"
        # Deliberately preserve raw metadata values. PDF and pdf are not
        # collapsed because case differences are themselves useful evidence.
        pdf_variants = []
        for name, count in counter.items():
            if str(name).casefold() == "pdf":
                try:
                    pdf_variants.append((str(name), int(count)))
                except (TypeError, ValueError):
                    pass
        if not pdf_variants:
            return f"{len(counter)} rå formatverdier (case beholdes)"
        pdf_variants.sort(key=lambda x: x[0])
        parts = " · ".join(f"{name}: {count:,}".replace(",", " ") for name, count in pdf_variants)
        return f"{len(counter)} rå formatverdier; case beholdes · {parts}"

    def _render_structured_controls(self, index: int) -> None:
        body = self._a1625_control_body
        parts = getattr(self, "_archive_parts", None) or []
        if body is None or not (0 <= index < len(parts)):
            return
        self._clear_control_body()
        row_data = parts[index]

        folder = self._values_for_row("folders", row_data)
        registration = self._values_for_row("registrations", row_data)
        journal = self._values_for_row("journalposts", row_data)
        description = self._values_for_row("descriptions", row_data)
        obj = self._values_for_row("objects", row_data)

        r = 0
        # Arkiv / arkivdeler
        box, rr = self._section(
            body, r, "Arkiv / arkivdeler",
            "Samme kontrollhierarki brukes for Alle arkivdeler og for valgt arkivdel.",
        )
        if row_data.get("is_all_archive_parts"):
            rr = self._control_row(box, rr, "Arkiv", "1", "depotrapport", "OK")
            rr = self._control_row(box, rr, "Arkivdeler", self._fmt_count(len(parts) - 1), "depotrapport", "OK")
        else:
            identity = row_data.get("archive_part") or {}
            rr = self._control_row(box, rr, "Arkivdel", str(identity.get("title") or "–"), "arkivstruktur.xml", "OK")
            rr = self._control_row(box, rr, "systemID", str(identity.get("system_id") or "–"), "arkivstruktur.xml", "OK")
        r += 1

        # Mapper / saker
        box, rr = self._section(body, r, "Mapper / saker")
        folder_types = folder.get("type_counts") or folder.get("folder_type_counts") or {}
        folder_count = folder.get("folder_count", row_data.get("folder_count"))
        case_count = self._counter_get(self._normalise_counter(folder_types), "saksmappe")
        if case_count is None:
            case_count = self._case_count_for_row(row_data)
        rr = self._control_row(box, rr, "Mapper", self._fmt_count(folder_count), "kdrs.c13", "OK")
        rr = self._control_row(box, rr, "Saker (saksmappe)", self._fmt_count(case_count), "kdrs.c13", "OK")
        rr = self._control_row(box, rr, "Mappetyper", self._counter_text(folder_types), "kdrs.c13", "OK")
        r += 1

        # Registreringer / journalposter
        box, rr = self._section(body, r, "Registreringer / journalposter")
        reg_types = registration.get("type_counts") or {}
        rr = self._control_row(
            box, rr, "Registreringer",
            self._fmt_count(registration.get("registration_count", row_data.get("registration_count"))),
            "kdrs.c14", "OK",
        )
        rr = self._control_row(
            box, rr, "Journalposter",
            self._fmt_count(journal.get("journalpost_count", row_data.get("journalpost_count"))),
            "kdrs.c15", "OK",
        )
        rr = self._control_row(box, rr, "Registreringstyper", self._counter_text(reg_types), "kdrs.c14", "OK")
        rr = self._control_row(
            box, rr, "Journalposttyper",
            self._counter_text(journal.get("journalpost_type_counts")),
            "kdrs.c15", "OK",
        )
        rr = self._control_row(
            box, rr, "Journalstatus",
            self._counter_text(journal.get("journal_status_counts")),
            "kdrs.c15", "OK",
        )
        r += 1

        # Dokumentbeskrivelser / dokumentobjekter
        box, rr = self._section(
            body, r, "Dokumentbeskrivelser / dokumentobjekter",
            "Dokumentmetadata holdes adskilt fra faktisk filformat/PRONOM. Rå metadata normaliseres ikke bort.",
        )
        rr = self._control_row(
            box, rr, "Dokumentbeskrivelser",
            self._fmt_count(description.get("document_description_count", row_data.get("document_description_count"))),
            "kdrs.c21", "OK",
        )
        rr = self._control_row(
            box, rr, "Dokumentobjekter",
            self._fmt_count(obj.get("document_object_count", row_data.get("document_object_count"))),
            "kdrs.c24", "OK",
        )
        rr = self._control_row(
            box, rr, "Tilknytning til registrering",
            self._counter_text(description.get("relation_type_counts")),
            "kdrs.c21", "OK",
        )
        rr = self._control_row(
            box, rr, "Dokumenttype",
            self._counter_text(description.get("document_type_counts"), limit=12),
            "kdrs.c21", "OK",
        )
        rr = self._control_row(
            box, rr, "Variantformat",
            self._counter_text(obj.get("variant_format_counts")),
            "kdrs.c24", "OK",
        )
        rr = self._control_row(
            box, rr, "Versjonsnummer",
            self._counter_text(obj.get("version_number_counts"), limit=12),
            "kdrs.c24", "OK",
        )
        rr = self._control_row(
            box, rr, "Format (metadata)",
            self._case_sensitive_format_note(obj.get("format_counts")),
            "kdrs.c24", "OBS",
        )
        r += 1

        # Bevaring etc stays visible, but separate from structural/document hierarchy.
        box, rr = self._section(body, r, "Bevaring, skjerming og kassasjon")
        for label, field, source in (
            ("Skjerminger", "screening_count", "kdrs.f08"),
            ("Kassasjonsvedtak", "disposal_decision_count", "kdrs.f10"),
            ("Utført kassasjon", "performed_disposal_count", "kdrs.f11"),
            ("Slettinger", "deletion_count", "kdrs.f13"),
        ):
            rr = self._control_row(box, rr, label, self._fmt_count(row_data.get(field)), source, "OK")

    def _render_a10_archive_part(self, index: int) -> None:
        super()._render_a10_archive_part(index)
        self._render_structured_controls(index)
