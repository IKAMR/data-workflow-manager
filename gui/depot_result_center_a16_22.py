from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_21 import DepotResultCenterDialogA16_21


class DepotResultCenterDialogA16_22(DepotResultCenterDialogA16_21):
    """a16.22: compact paired counts in the top-level Oversikt."""

    @staticmethod
    def _fmt_count(value) -> str:
        if value is None or value == "":
            return "–"
        try:
            return f"{int(value):,}".replace(",", " ")
        except (TypeError, ValueError):
            return str(value)

    def _summary_value(self, *keys):
        summary = self.model.get("summary") or {}
        for key in keys:
            value = summary.get(key)
            if value is not None:
                return value
        return None

    def _build_overview_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        summary = self.model.get("summary") or {}
        real_parts = [
            row for row in (self.model.get("archive_parts") or [])
            if not row.get("is_all_archive_parts")
        ]
        deviations = list(self.model.get("deviations") or [])
        technical = self.model.get("technical_validation") or {}
        arkade = ((self.model.get("external_validation") or {}).get("arkade5") or {})
        pronom = arkade.get("pronom_summary") or {}

        ctk.CTkLabel(
            tab,
            text="Oversikt",
            anchor="w",
            font=theme.font(theme.HEADER_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        archive_count = self._summary_value("archive_count")
        archive_part_count = self._summary_value("archive_part_count")
        if archive_part_count is None:
            archive_part_count = len(real_parts)

        folder_count = self._summary_value("folder_count")
        # Saksmapper are not yet a materialized summary field.  Keep this
        # deliberately unknown rather than treating every mappe as a sak.
        case_count = self._summary_value(
            "case_count", "case_folder_count", "folder_case_count", "sak_count"
        )

        pairs = (
            (archive_count, archive_part_count, "Arkiv / arkivdeler"),
            (folder_count, case_count, "Mapper / saker"),
            (
                self._summary_value("registration_count"),
                self._summary_value("journalpost_count"),
                "Registreringer / JP",
            ),
            (
                self._summary_value("document_description_count"),
                self._summary_value("document_object_count"),
                "Dok.beskrivelser / objekter",
            ),
        )

        cards = ctk.CTkFrame(tab, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        for col in range(4):
            cards.grid_columnconfigure(col, weight=1, uniform="a1622overview")

        for col, (left, right, label) in enumerate(pairs):
            card = ctk.CTkFrame(cards)
            card.grid(row=0, column=col, sticky="nsew", padx=4)
            ctk.CTkLabel(
                card,
                text=f"{self._fmt_count(left)} / {self._fmt_count(right)}",
                anchor="w",
                font=theme.font(theme.TITLE_SIZE, weight="bold"),
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(9, 1))
            ctk.CTkLabel(
                card,
                text=label,
                anchor="w",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 9))

        box = ctk.CTkTextbox(tab, wrap="word", font=theme.font(theme.SMALL_SIZE))
        box.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        status = technical.get("status") or "–"
        imports = len(arkade.get("imports") or [])
        lines = [
            "SAMLET RESULTATOVERSIKT",
            "",
            f"Teknisk status: {status}",
            f"Arkivdeler: {self._fmt_count(archive_part_count)}",
            f"Vurderingspunkter: {len(deviations)}",
            f"Arkade 5-kjøringer: {imports}",
            f"PRONOM-statistikkrader: {pronom.get('statistics_rows', 0)}",
            "",
            "Saker vises som – inntil antall mapper av type sak er materialisert i resultatgrunnlaget.",
            "Bruk Arkivdeler for vurdering per arkivdel, Teknisk for kontroller,",
            "Filformater for PRONOM/Siegfried og Depotvurdering for faglig konklusjon.",
        ]
        box.insert("1.0", "\n".join(lines))
        box.configure(state="disabled")
