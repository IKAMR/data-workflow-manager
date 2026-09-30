from __future__ import annotations

from .depot_result_center_a23_4 import DepotResultCenterDialogA23_4


class DepotResultCenterDialogA23_5(DepotResultCenterDialogA23_4):
    """a23.5: extend structured evidence to Journalstatus and Registreringstyper."""

    @staticmethod
    def _a235_first_counter(values: dict, *keys: str) -> dict:
        for key in keys:
            candidate = values.get(key)
            if isinstance(candidate, dict):
                return candidate
        return {}

    def _a235_render_journal_status(self, parent, row: dict, item: dict) -> None:
        journal = self._values_for_row("journalposts", row)
        values = self._a235_first_counter(
            journal,
            "journalstatus_counts",
            "journal_status_counts",
            "status_counts",
        )
        rows = self._a231_counter_rows(values, limit=100)
        self._a232_card(parent, 0, "Kontrollgrunnlag", [
            ("Journalposter totalt", self._fmt_count(journal.get("journalpost_count", row.get("journalpost_count")))),
            ("Kontrollstatus", str(item.get("control_status") or "–")),
            ("Kilde", str(item.get("source") or "–")),
            ("Registrerte journalstatuser", self._fmt_count(len(rows))),
        ], columns=2)
        self._a233_distribution(parent, 1, "Journalstatus – materialisert fordeling", rows, limit=18)
        self._a233_support_note(parent, 2, "Vurderingsstøtte", [
            "Fordelingen viser hvilke journalstatuser som faktisk forekommer i valgt arkivdel.",
            "Uventede eller sjeldne statuser kan dokumenteres i faglig vurdering til høyre.",
            "Tallene leses fra materialisert kontrollgrunnlag; visningen kjører ingen ny analyse.",
        ])

    def _a235_render_registration_types(self, parent, row: dict, item: dict) -> None:
        registrations = self._values_for_row("registrations", row)
        values = self._a235_first_counter(
            registrations,
            "registration_type_counts",
            "registreringstype_counts",
            "type_counts",
        )
        rows = self._a231_counter_rows(values, limit=100)
        self._a232_card(parent, 0, "Kontrollgrunnlag", [
            ("Registreringer totalt", self._fmt_count(registrations.get("registration_count", row.get("registration_count")))),
            ("Kontrollstatus", str(item.get("control_status") or "–")),
            ("Kilde", str(item.get("source") or "–")),
            ("Registrerte registreringstyper", self._fmt_count(len(rows))),
        ], columns=2)
        self._a233_distribution(parent, 1, "Registreringstyper – materialisert fordeling", rows, limit=18)
        self._a233_support_note(parent, 2, "Vurderingsstøtte", [
            "Fordelingen viser hvilke registreringstyper som faktisk forekommer i valgt arkivdel.",
            "Fordelingen kan brukes sammen med journalposttyper og journalstatus ved faglig vurdering.",
            "Visningen endrer ikke kildedata og starter ingen ny analyse.",
        ])

    def _a232_render_evidence(self, parent, index: int, item: dict) -> None:
        label = str(item.get("label") or "")
        parts = getattr(self, "_archive_parts", None) or []
        if 0 <= index < len(parts):
            row = parts[index]
            if label == "Journalstatus":
                self._a232_clear(parent)
                self._a235_render_journal_status(parent, row, item)
                return
            if label == "Registreringstyper":
                self._a232_clear(parent)
                self._a235_render_registration_types(parent, row, item)
                return
        return super()._a232_render_evidence(parent, index, item)
