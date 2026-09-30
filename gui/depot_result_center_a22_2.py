from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from . import theme
from .depot_result_center_a22_1 import DepotResultCenterDialogA22_1


class DepotResultCenterDialogA22_2(DepotResultCenterDialogA22_1):
    """a22.2: interactive control treatment and structured review points.

    Depot review is kept beside the generated report.  Source facts and the
    materialized control results are never rewritten by this surface.
    """

    REVIEW_STATUSES = (
        "Ikke vurdert",
        "OK",
        "Akseptert avvik",
        "Krever avklaring",
        "Ikke relevant",
    )

    def __init__(self, master, **kwargs) -> None:
        self._a222_reviews: dict[str, dict] = {}
        self._a222_control_section = ""
        self._a222_review_body = None
        self._a222_control_window = None
        super().__init__(master, **kwargs)
        self._a222_load_reviews()
        self._a222_rebuild_archive_review_tab()
        if getattr(self, "_archive_parts", None):
            self._render_structured_controls(getattr(self, "_archive_index", 0))
            self._a222_render_review_points(getattr(self, "_archive_index", 0))

    # ------------------------------------------------------------------
    # Review sidecar: separate treatment state from canonical report facts.
    # ------------------------------------------------------------------
    def _a222_review_path(self) -> Path | None:
        report_path = getattr(self, "report_path", None)
        if report_path is None:
            return None
        path = Path(report_path)
        return path.with_name(path.stem + ".control_review.json")

    def _a222_load_reviews(self) -> None:
        path = self._a222_review_path()
        self._a222_reviews = {}
        if path is None or not path.is_file():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            items = payload.get("reviews") or {}
            if isinstance(items, dict):
                self._a222_reviews = items
        except Exception:
            self._a222_reviews = {}

    def _a222_save_reviews(self) -> None:
        path = self._a222_review_path()
        if path is None:
            raise RuntimeError("Ingen depotrapport er koblet til visningen.")
        payload = {
            "schema": "dwm.control-review.v1",
            "report": str(getattr(self, "report_path", "") or ""),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "reviews": self._a222_reviews,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _a222_archive_key(self, index: int) -> str:
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)):
            return "unknown"
        row = parts[index]
        if row.get("is_all_archive_parts"):
            return "__ALL_ARCHIVE_PARTS__"
        identity = row.get("archive_part") or {}
        return str(identity.get("system_id") or f"archive-{index}")

    @staticmethod
    def _a222_control_key(section: str, label: str, source: str) -> str:
        return " | ".join((str(section).strip(), str(label).strip(), str(source).strip()))

    def _a222_review_for(self, index: int, section: str, label: str, source: str) -> dict:
        archive = self._a222_archive_key(index)
        key = self._a222_control_key(section, label, source)
        return dict((self._a222_reviews.get(archive) or {}).get(key) or {})

    def _a222_set_review(self, index: int, item: dict, status: str, comment: str) -> None:
        archive = self._a222_archive_key(index)
        key = self._a222_control_key(item["section"], item["label"], item["source"])
        username = ""
        user = getattr(self, "user", None)
        if user is not None:
            username = str(getattr(user, "username", "") or getattr(user, "user_id", "") or "")
        bucket = self._a222_reviews.setdefault(archive, {})
        bucket[key] = {
            "archive_key": archive,
            "section": item["section"],
            "label": item["label"],
            "value": item["value"],
            "source": item["source"],
            "control_status": item["control_status"],
            "review_status": status,
            "comment": comment.strip(),
            "user": username,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._a222_save_reviews()

    # ------------------------------------------------------------------
    # Structured controls: keep the existing table, add treatment summary.
    # ------------------------------------------------------------------
    def _build_controls_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 5))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Kontroller for valgt arkivdel",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            header,
            text="Åpne behandlingsvindu",
            width=175,
            command=self._a222_open_control_window,
        ).grid(row=0, column=1, padx=(10, 0))

        self._a1625_control_body = ctk.CTkScrollableFrame(tab)
        self._a1625_control_body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._a1625_control_body.grid_columnconfigure(0, weight=1)
        self._a10_controls = ctk.CTkTextbox(tab, width=1, height=1)

    def _section(self, parent, row: int, title: str, subtitle: str = ""):
        self._a222_control_section = title
        box = ctk.CTkFrame(parent)
        box.grid(row=row, column=0, sticky="ew", padx=2, pady=(3, 7))
        box.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            box, text=title, anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, columnspan=5, sticky="ew", padx=10, pady=(8, 1))
        if subtitle:
            ctk.CTkLabel(
                box, text=subtitle, anchor="w",
                text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 6))
            header_row = 2
        else:
            header_row = 1

        headers = ("Kontroll", "Resultat / verdi", "Kilde", "Status", "Behandling")
        widths = (190, 490, 95, 65, 150)
        for col, (label, width) in enumerate(zip(headers, widths)):
            box.grid_columnconfigure(col, weight=1 if col == 1 else 0)
            ctk.CTkLabel(
                box, text=label, width=width, anchor="w",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=header_row, column=col, sticky="ew", padx=(10 if col == 0 else 4, 4), pady=(2, 4))
        return box, header_row + 1

    def _control_row(self, box, row: int, label: str, value: str, source: str, status: str = "OK") -> int:
        index = int(getattr(self, "_archive_index", 0) or 0)
        review = self._a222_review_for(index, self._a222_control_section, label, source)
        review_status = str(review.get("review_status") or "Ikke vurdert")
        comment = str(review.get("comment") or "").strip()
        treatment = review_status + (" · kommentar" if comment else "")
        values = (label, value, source, status, treatment)
        for col, text in enumerate(values):
            ctk.CTkLabel(
                box,
                text=text,
                anchor="w",
                justify="left",
                wraplength=600 if col == 1 else 190,
                text_color=theme.TEXT_SUB if col != 4 else theme.TEXT_MAIN,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=row, column=col, sticky="ew", padx=(10 if col == 0 else 4, 4), pady=2)
        return row + 1

    # ------------------------------------------------------------------
    # One canonical list of visible control rows for the treatment dialog.
    # ------------------------------------------------------------------
    def _a222_control_items(self, index: int) -> list[dict]:
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)):
            return []
        row = parts[index]
        items: list[dict] = []

        def add(section, label, value, source, control_status="OK"):
            items.append({
                "section": section,
                "label": label,
                "value": str(value),
                "source": source,
                "control_status": control_status,
            })

        if row.get("is_all_archive_parts"):
            add("Arkiv / arkivdeler", "Arkiv", "1", "depotrapport")
            add("Arkiv / arkivdeler", "Arkivdeler", self._fmt_count(max(0, len(parts) - 1)), "depotrapport")
        else:
            identity = row.get("archive_part") or {}
            add("Arkiv / arkivdeler", "Arkivdel", identity.get("title") or "–", "arkivstruktur.xml")
            add("Arkiv / arkivdeler", "systemID", identity.get("system_id") or "–", "arkivstruktur.xml")

        folder = self._values_for_row("folders", row)
        folder_types = folder.get("type_counts") or folder.get("folder_type_counts") or {}
        case_count = self._counter_get(self._normalise_counter(folder_types), "saksmappe")
        if case_count is None:
            case_count = self._case_count_for_row(row)
        add("Mapper / saker", "Mapper", self._fmt_count(folder.get("folder_count", row.get("folder_count"))), "kdrs.c13")
        add("Mapper / saker", "Saker (saksmappe)", self._fmt_count(case_count), "kdrs.c13")
        add("Mapper / saker", "Mappetyper", self._counter_text(folder_types), "kdrs.c13")

        registration = self._values_for_row("registrations", row)
        journal = self._values_for_row("journalposts", row)
        add("Registreringer / journalposter", "Registreringer", self._fmt_count(registration.get("registration_count", row.get("registration_count"))), "kdrs.c14")
        add("Registreringer / journalposter", "Journalposter", self._fmt_count(journal.get("journalpost_count", row.get("journalpost_count"))), "kdrs.c15")
        add("Registreringer / journalposter", "Registreringstyper", self._counter_text(registration.get("type_counts") or {}), "kdrs.c14")
        add("Registreringer / journalposter", "Journalposttyper", self._counter_text(journal.get("journalpost_type_counts")), "kdrs.c15")
        add("Registreringer / journalposter", "Journalstatus", self._counter_text(journal.get("journal_status_counts")), "kdrs.c15")

        description = self._values_for_row("descriptions", row)
        obj = self._values_for_row("objects", row)
        section = "Dokumentbeskrivelser / dokumentobjekter"
        add(section, "Dokumentbeskrivelser", self._fmt_count(description.get("document_description_count", row.get("document_description_count"))), "kdrs.c21")
        add(section, "Dokumentobjekter", self._fmt_count(obj.get("document_object_count", row.get("document_object_count"))), "kdrs.c24")
        add(section, "Tilknytning til registrering", self._counter_text(description.get("relation_type_counts")), "kdrs.c21")
        add(section, "Dokumenttype", self._counter_text(description.get("document_type_counts"), limit=12), "kdrs.c21")
        add(section, "Variantformat", self._counter_text(obj.get("variant_format_counts")), "kdrs.c24")
        add(section, "Versjonsnummer", self._counter_text(obj.get("version_number_counts"), limit=12), "kdrs.c24")
        add(section, "Format (metadata)", self._case_sensitive_format_note(obj.get("format_counts")), "kdrs.c24", "OBS")

        for label, field, source in (
            ("Skjerminger", "screening_count", "kdrs.f08"),
            ("Kassasjonsvedtak", "disposal_decision_count", "kdrs.f10"),
            ("Utført kassasjon", "performed_disposal_count", "kdrs.f11"),
            ("Slettinger", "deletion_count", "kdrs.f13"),
        ):
            add("Bevaring, skjerming og kassasjon", label, self._fmt_count(row.get(field)), source)
        return items

    # ------------------------------------------------------------------
    # Treatment dialog: click control -> status/comment -> persist.
    # ------------------------------------------------------------------
    def _a222_open_control_window(self) -> None:
        existing = getattr(self, "_a222_control_window", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                pass

        index = int(getattr(self, "_archive_index", 0) or 0)
        items = self._a222_control_items(index)
        win = ctk.CTkToplevel(self)
        self._a222_control_window = win
        win.title("Behandle kontroller – Noark 5")
        win.geometry("1180x720")
        win.minsize(900, 600)
        win.transient(self)
        win.grid_columnconfigure(1, weight=1)
        win.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            win,
            text="Kontrollbehandling",
            anchor="w",
            font=theme.font(theme.HEADER_SIZE, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(12, 6))

        left = ctk.CTkScrollableFrame(win, width=330)
        left.grid(row=1, column=0, sticky="nsew", padx=(14, 7), pady=(0, 14))
        right = ctk.CTkFrame(win)
        right.grid(row=1, column=1, sticky="nsew", padx=(7, 14), pady=(0, 14))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(5, weight=1)

        selected = {"item": None}
        title = ctk.CTkLabel(right, text="Velg en kontroll", anchor="w", font=theme.font(theme.TITLE_SIZE, weight="bold"))
        title.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 3))
        detail = ctk.CTkLabel(right, text="", anchor="nw", justify="left", wraplength=720, text_color=theme.TEXT_SUB, font=theme.font(theme.SMALL_SIZE))
        detail.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        ctk.CTkLabel(right, text="Vurderingsstatus", anchor="w", font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(row=2, column=0, sticky="ew", padx=14)
        status_var = ctk.StringVar(value="Ikke vurdert")
        status = ctk.CTkOptionMenu(right, variable=status_var, values=list(self.REVIEW_STATUSES))
        status.grid(row=3, column=0, sticky="ew", padx=14, pady=(3, 10))
        ctk.CTkLabel(right, text="Kommentar / faglig behandling", anchor="w", font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(row=4, column=0, sticky="ew", padx=14)
        comment = ctk.CTkTextbox(right, wrap="word", font=theme.font(theme.SMALL_SIZE))
        comment.grid(row=5, column=0, sticky="nsew", padx=14, pady=(3, 10))

        def choose(item):
            selected["item"] = item
            title.configure(text=item["label"])
            detail.configure(text=f"Seksjon: {item['section']}\nKilde: {item['source']}\nKontrollstatus: {item['control_status']}\nResultat: {item['value']}")
            review = self._a222_review_for(index, item["section"], item["label"], item["source"])
            status_var.set(str(review.get("review_status") or "Ikke vurdert"))
            comment.delete("1.0", "end")
            comment.insert("1.0", str(review.get("comment") or ""))

        current_section = None
        rr = 0
        for item in items:
            if item["section"] != current_section:
                current_section = item["section"]
                ctk.CTkLabel(left, text=current_section, anchor="w", font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(row=rr, column=0, sticky="ew", padx=6, pady=(10, 3))
                rr += 1
            existing_review = self._a222_review_for(index, item["section"], item["label"], item["source"])
            suffix = str(existing_review.get("review_status") or "")
            text = item["label"] + (f"  ·  {suffix}" if suffix and suffix != "Ikke vurdert" else "")
            ctk.CTkButton(left, text=text, anchor="w", height=30, command=lambda i=item: choose(i)).grid(row=rr, column=0, sticky="ew", padx=4, pady=2)
            rr += 1

        def save_current():
            item = selected.get("item")
            if item is None:
                messagebox.showinfo("Data Workflow Manager", "Velg en kontroll først.", parent=win)
                return
            try:
                self._a222_set_review(index, item, status_var.get(), comment.get("1.0", "end"))
            except Exception as exc:
                messagebox.showerror("Data Workflow Manager", str(exc), parent=win)
                return
            self._render_structured_controls(index)
            self._a222_render_review_points(index)
            messagebox.showinfo("Data Workflow Manager", "Vurderingen er lagret.", parent=win)

        ctk.CTkButton(right, text="Lagre vurdering", width=145, command=save_current).grid(row=6, column=0, sticky="e", padx=14, pady=(0, 14))
        if items:
            choose(items[0])

    # ------------------------------------------------------------------
    # Vurderingspunkter: matrix/collection rather than one free text field.
    # ------------------------------------------------------------------
    def _a222_rebuild_archive_review_tab(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None:
            return
        try:
            tab = tabs.tab("Vurderingspunkter")
        except Exception:
            return
        for child in tab.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            tab,
            text="Vurderingspunkter – samlet behandling",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        self._a222_review_body = ctk.CTkScrollableFrame(tab)
        self._a222_review_body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._a222_review_body.grid_columnconfigure(0, weight=1)

    def _a222_visible_reviews(self, index: int) -> list[dict]:
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)):
            return []
        row = parts[index]
        if row.get("is_all_archive_parts"):
            buckets = list(self._a222_reviews.values())
        else:
            buckets = [self._a222_reviews.get(self._a222_archive_key(index)) or {}]
        records = []
        for bucket in buckets:
            for record in bucket.values():
                status = str(record.get("review_status") or "Ikke vurdert")
                comment = str(record.get("comment") or "").strip()
                if status != "Ikke vurdert" or comment:
                    records.append(dict(record))
        records.sort(key=lambda r: (str(r.get("section") or ""), str(r.get("label") or ""), str(r.get("archive_key") or "")))
        return records

    def _a222_render_review_points(self, index: int) -> None:
        body = getattr(self, "_a222_review_body", None)
        if body is None:
            return
        for child in body.winfo_children():
            child.destroy()
        records = self._a222_visible_reviews(index)
        if not records:
            ctk.CTkLabel(
                body,
                text=("Ingen behandlede kontrollpunkter ennå. Åpne Kontroller → Åpne behandlingsvindu "
                      "for å registrere faglig status og kommentar."),
                anchor="w", justify="left", wraplength=980,
                text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE),
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=10)
            return

        row_no = 0
        section = None
        for record in records:
            if record.get("section") != section:
                section = record.get("section")
                ctk.CTkLabel(body, text=str(section), anchor="w", font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(row=row_no, column=0, sticky="ew", padx=8, pady=(10, 4))
                row_no += 1
            card = ctk.CTkFrame(body)
            card.grid(row=row_no, column=0, sticky="ew", padx=6, pady=3)
            card.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(card, text=str(record.get("label") or "Kontroll"), anchor="w", font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(row=0, column=0, sticky="nw", padx=10, pady=(7, 2))
            ctk.CTkLabel(card, text=str(record.get("review_status") or "Ikke vurdert"), anchor="e", font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(row=0, column=1, sticky="ne", padx=10, pady=(7, 2))
            meta = f"Kilde: {record.get('source') or '–'} · Kontrollstatus: {record.get('control_status') or '–'}"
            ctk.CTkLabel(card, text=meta, anchor="w", text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE)).grid(row=1, column=0, columnspan=2, sticky="ew", padx=10)
            ctk.CTkLabel(card, text=str(record.get("value") or "–"), anchor="w", justify="left", wraplength=980, text_color=theme.TEXT_SUB, font=theme.font(theme.SMALL_SIZE)).grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 2))
            comment = str(record.get("comment") or "").strip()
            if comment:
                ctk.CTkLabel(card, text=comment, anchor="w", justify="left", wraplength=980, font=theme.font(theme.SMALL_SIZE)).grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 7))
            row_no += 1

    # ------------------------------------------------------------------
    # Technical reference: responsive multi-column surface, no new analysis.
    # ------------------------------------------------------------------
    def _build_technical_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            tab, text="Teknisk resultatgrunnlag", anchor="w",
            font=theme.font(theme.HEADER_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._a222_technical_body = body
        specs = (
            ("Noark 5-tester", self._technical_text()),
            ("Vurderingspunkter", self._review_text()),
            ("Arkade 5", self._arkade_text()),
        )
        self._a222_technical_cards = []
        for title, text in specs:
            card = ctk.CTkFrame(body)
            card.grid_columnconfigure(0, weight=1)
            card.grid_rowconfigure(1, weight=1)
            ctk.CTkLabel(card, text=title, anchor="w", font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
            box = ctk.CTkTextbox(card, wrap="word", font=theme.font(theme.SMALL_SIZE))
            box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
            box.insert("1.0", text)
            box.configure(state="disabled")
            self._a222_technical_cards.append(card)
        body.bind("<Configure>", self._a222_reflow_technical, add="+")
        self.after_idle(lambda: self._a222_reflow_technical(None))

    def _a222_reflow_technical(self, _event) -> None:
        body = getattr(self, "_a222_technical_body", None)
        cards = getattr(self, "_a222_technical_cards", None) or []
        if body is None or not cards:
            return
        try:
            width = max(1, int(body.winfo_width()))
        except Exception:
            width = 1000
        columns = 3 if width >= 1350 else (2 if width >= 900 else 1)
        for col in range(3):
            body.grid_columnconfigure(col, weight=1 if col < columns else 0, uniform="a222tech")
        rows = (len(cards) + columns - 1) // columns
        for row in range(rows):
            body.grid_rowconfigure(row, weight=1, uniform="a222techrow")
        for i, card in enumerate(cards):
            r, c = divmod(i, columns)
            card.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._a222_render_review_points(index)
