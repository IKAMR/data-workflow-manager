from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a23_2 import DepotResultCenterDialogA23_2


class DepotResultCenterDialogA23_3(DepotResultCenterDialogA23_2):
    """a23.3: structured evidence for representative distribution controls.

    a23.2 established the visual evidence pattern for Arkivdel. a23.3 extends
    the same pattern to Mappetyper, Journalposttyper and Format (metadata),
    still using only already materialized report data.
    """

    def _a233_distribution(self, parent, row: int, title: str, rows: list[tuple[str, int]], *, limit: int = 12) -> None:
        card = ctk.CTkFrame(parent, fg_color=theme.CARD_BG, border_width=1, border_color=theme.CARD_BORDER)
        card.grid(row=row, column=0, sticky="ew", padx=2, pady=(0, 8))
        card.grid_columnconfigure(0, weight=3)
        card.grid_columnconfigure(1, weight=0)
        card.grid_columnconfigure(2, weight=2)

        ctk.CTkLabel(
            card,
            text=title,
            anchor="w",
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(8, 5))

        shown = list(rows[:limit])
        if not shown:
            ctk.CTkLabel(
                card,
                text="Ingen materialiserte fordelingsverdier.",
                anchor="w",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(2, 10))
            return

        total = sum(max(0, int(count or 0)) for _name, count in rows)
        maximum = max((max(0, int(count or 0)) for _name, count in shown), default=1) or 1
        for idx, (name, count) in enumerate(shown, start=1):
            count = max(0, int(count or 0))
            share = (count / total * 100.0) if total else 0.0
            ctk.CTkLabel(
                card,
                text=str(name),
                anchor="w",
                justify="left",
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=idx, column=0, sticky="ew", padx=(10, 8), pady=3)
            ctk.CTkLabel(
                card,
                text=f"{self._fmt_count(count)}   {share:5.1f} %",
                anchor="e",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=idx, column=1, sticky="e", padx=(0, 8), pady=3)
            bar = ctk.CTkProgressBar(card, height=8)
            bar.grid(row=idx, column=2, sticky="ew", padx=(0, 10), pady=3)
            bar.set(count / maximum if maximum else 0)

        footer_row = len(shown) + 1
        extra = len(rows) - len(shown)
        footer = f"Sum: {self._fmt_count(total)}"
        if extra > 0:
            footer += f"   ·   + {extra} flere verdier"
        ctk.CTkLabel(
            card,
            text=footer,
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=footer_row, column=0, columnspan=3, sticky="ew", padx=10, pady=(5, 8))

    def _a233_support_note(self, parent, row: int, title: str, lines: list[str]) -> None:
        card = ctk.CTkFrame(parent, fg_color=theme.CARD_BG, border_width=1, border_color=theme.CARD_BORDER)
        card.grid(row=row, column=0, sticky="ew", padx=2, pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card,
            text=title,
            anchor="w",
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        for idx, line in enumerate(lines, start=1):
            ctk.CTkLabel(
                card,
                text=f"• {line}",
                anchor="w",
                justify="left",
                wraplength=660,
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=idx, column=0, sticky="ew", padx=10, pady=(1, 3))
        card.grid_rowconfigure(len(lines) + 1, minsize=5)

    def _a233_render_folder_types(self, parent, row: dict, item: dict) -> None:
        folder = self._values_for_row("folders", row)
        values = folder.get("type_counts") or folder.get("folder_type_counts") or {}
        rows = self._a231_counter_rows(values, limit=50)
        self._a232_card(parent, 0, "Kontrollgrunnlag", [
            ("Mapper totalt", self._fmt_count(folder.get("folder_count", row.get("folder_count")))),
            ("Kontrollstatus", str(item.get("control_status") or "–")),
            ("Kilde", str(item.get("source") or "–")),
            ("Registrerte mappetyper", self._fmt_count(len(rows))),
        ], columns=2)
        self._a233_distribution(parent, 1, "Mappetyper – materialisert fordeling", rows, limit=14)
        self._a233_support_note(parent, 2, "Vurderingsstøtte", [
            "Fordelingen viser hvilke mappetyper som faktisk forekommer i valgt arkivdel.",
            "Uventede, tomme eller dominerende typer kan kommenteres i faglig vurdering til høyre.",
            "Visningen kjører ingen ny analyse; tallene kommer fra materialisert kontrollgrunnlag.",
        ])

    def _a233_render_journalpost_types(self, parent, row: dict, item: dict) -> None:
        journal = self._values_for_row("journalposts", row)
        values = journal.get("journalpost_type_counts") or {}
        rows = self._a231_counter_rows(values, limit=50)
        self._a232_card(parent, 0, "Kontrollgrunnlag", [
            ("Journalposter totalt", self._fmt_count(journal.get("journalpost_count", row.get("journalpost_count")))),
            ("Kontrollstatus", str(item.get("control_status") or "–")),
            ("Kilde", str(item.get("source") or "–")),
            ("Registrerte journalposttyper", self._fmt_count(len(rows))),
        ], columns=2)
        self._a233_distribution(parent, 1, "Journalposttyper – materialisert fordeling", rows, limit=14)
        self._a233_support_note(parent, 2, "Vurderingsstøtte", [
            "Fordelingen gir et raskt bilde av hvilke journalposttyper som brukes i arkivdelen.",
            "Uventede kombinasjoner eller verdier kan dokumenteres som faglig vurdering.",
            "Kontrollen endrer ikke kildedata eller det materialiserte resultatet.",
        ])

    def _a233_render_format_metadata(self, parent, row: dict, item: dict) -> None:
        obj = self._values_for_row("objects", row)
        values = obj.get("format_counts") or {}
        rows = self._a231_counter_rows(values, limit=100)
        self._a232_card(parent, 0, "Kontrollgrunnlag", [
            ("Dokumentobjekter totalt", self._fmt_count(obj.get("document_object_count", row.get("document_object_count")))),
            ("Kontrollstatus", str(item.get("control_status") or "–")),
            ("Kilde", str(item.get("source") or "–")),
            ("Unike metadataverdier", self._fmt_count(len(rows))),
        ], columns=2)
        self._a233_distribution(parent, 1, "Format (metadata) – materialiserte verdier", rows, limit=18)
        self._a233_support_note(parent, 2, "Viktig skille", [
            "Dette er metadatafeltet format i Noark 5-uttrekket, ikke PRONOM-identifikasjon av de fysiske filene.",
            "Store variasjoner i skrivemåte eller rå formatverdier kan være relevante vurderingspunkter.",
            "Sammenligning mot Filformater / PRONOM beholdes som en egen senere kontrollflate.",
        ])

    def _a232_render_evidence(self, parent, index: int, item: dict) -> None:
        self._a232_clear(parent)
        parts = getattr(self, "_archive_parts", None) or []
        label = str(item.get("label") or "")
        if not (0 <= index < len(parts)):
            return super()._a232_render_evidence(parent, index, item)

        row = parts[index]
        if label == "Arkivdel":
            self._a232_render_archive_part(parent, index, row, item)
            return
        if label == "Mappetyper":
            self._a233_render_folder_types(parent, row, item)
            return
        if label == "Journalposttyper":
            self._a233_render_journalpost_types(parent, row, item)
            return
        if label == "Format (metadata)":
            self._a233_render_format_metadata(parent, row, item)
            return

        return super()._a232_render_evidence(parent, index, item)
