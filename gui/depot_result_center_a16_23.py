from __future__ import annotations

import json
from pathlib import Path

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_22 import DepotResultCenterDialogA16_22


class DepotResultCenterDialogA16_23(DepotResultCenterDialogA16_22):
    """a16.23: paired overview and real saksmappe counts from materialized XPath results."""

    def __init__(self, master, **kwargs) -> None:
        self._a1623_case_total = None
        self._a1623_case_by_part: dict[str, int] = {}
        self._a1623_case_loaded = False
        super().__init__(master, **kwargs)

    # ------------------------------------------------------------------
    # Existing materialized XPath evidence -- no XML/XPath recalculation.
    # ------------------------------------------------------------------
    @staticmethod
    def _counter_value(counter, wanted: str):
        if not isinstance(counter, dict):
            return None
        wanted_cf = wanted.casefold()
        for key, value in counter.items():
            if str(key).strip().casefold() == wanted_cf:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return value
        return None

    def _load_case_counts(self) -> None:
        if self._a1623_case_loaded:
            return
        self._a1623_case_loaded = True

        evidence = self.model.get("evidence") or {}
        xpath_run = str(evidence.get("source_xpath_run") or "").strip()
        if not xpath_run:
            return

        path = Path(xpath_run) / "results" / "kdrs_c13.json"
        if not path.is_file():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return

        values = payload.get("values") or {}
        self._a1623_case_total = self._counter_value(values.get("type_counts"), "saksmappe")

        by_part: dict[str, int] = {}
        for item in values.get("_archive_parts") or []:
            identity = item.get("archive_part") or {}
            system_id = str(identity.get("system_id") or "").strip()
            if not system_id:
                continue
            part_values = item.get("values") or {}
            count = self._counter_value(part_values.get("type_counts"), "saksmappe")
            if count is not None:
                by_part[system_id] = count
        self._a1623_case_by_part = by_part

    def _case_count_whole(self):
        self._load_case_counts()
        if self._a1623_case_total is not None:
            return self._a1623_case_total
        return self._summary_value(
            "case_count", "case_folder_count", "folder_case_count", "sak_count"
        )

    def _case_count_for_row(self, row: dict):
        self._load_case_counts()
        if row.get("is_all_archive_parts"):
            return self._a1623_case_total
        identity = row.get("archive_part") or {}
        system_id = str(identity.get("system_id") or "").strip()
        if system_id and system_id in self._a1623_case_by_part:
            return self._a1623_case_by_part[system_id]
        for key in ("case_count", "case_folder_count", "folder_case_count", "sak_count"):
            value = row.get(key)
            if value is not None:
                return value
        return None

    # ------------------------------------------------------------------
    # Oversikt
    # ------------------------------------------------------------------
    def _build_overview_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

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

        pairs = (
            (archive_count, archive_part_count, "Arkiv / arkivdeler"),
            (self._summary_value("folder_count"), self._case_count_whole(), "Mapper / saker"),
            (
                self._summary_value("registration_count"),
                self._summary_value("journalpost_count"),
                "Registreringer / journalposter",
            ),
            (
                self._summary_value("document_description_count"),
                self._summary_value("document_object_count"),
                "Dokumentbeskrivelser / objekter",
            ),
        )

        cards = ctk.CTkFrame(tab, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        for col in range(4):
            cards.grid_columnconfigure(col, weight=1, uniform="a1623overview")

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
            f"Arkiv: {self._fmt_count(archive_count)}",
            f"Arkivdeler: {self._fmt_count(archive_part_count)}",
            f"Vurderingspunkter: {len(deviations)}",
            f"Arkade 5-kjøringer: {imports}",
            f"PRONOM-statistikkrader: {pronom.get('statistics_rows', 0)}",
            "",
            "Saker leses fra allerede materialisert N5.15 / kdrs.c13 (mapper av type saksmappe).",
            "Bruk Arkivdeler for vurdering per arkivdel, Teknisk for kontroller,",
            "Filformater for PRONOM/Siegfried og Depotvurdering for faglig konklusjon.",
        ]
        box.insert("1.0", "\n".join(lines))
        box.configure(state="disabled")

    # ------------------------------------------------------------------
    # Arkivdeler -> Sammendrag -> Innhold og omfang
    # ------------------------------------------------------------------
    def _render_a10_archive_part(self, index: int) -> None:
        super()._render_a10_archive_part(index)
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)) or not hasattr(self, "_a10_content"):
            return
        row = parts[index]
        lines = [
            f"Mapper: {self._fmt_count(row.get('folder_count'))}",
            f"Saker: {self._fmt_count(self._case_count_for_row(row))}",
            f"Registreringer: {self._fmt_count(row.get('registration_count'))}",
            f"Journalposter: {self._fmt_count(row.get('journalpost_count'))}",
            f"Dokumentbeskrivelser: {self._fmt_count(row.get('document_description_count'))}",
            f"Dokumentobjekter: {self._fmt_count(row.get('document_object_count'))}",
            f"Skjerminger: {self._fmt_count(row.get('screening_count'))}",
            f"Kassasjonsvedtak: {self._fmt_count(row.get('disposal_decision_count'))}",
            f"Utført kassasjon: {self._fmt_count(row.get('performed_disposal_count'))}",
            f"Slettinger: {self._fmt_count(row.get('deletion_count'))}",
        ]
        self._a10_content.configure(text="\n".join(lines))
