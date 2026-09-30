from __future__ import annotations

from .depot_result_center_a23_9 import DepotResultCenterDialogA23_9


class DepotResultCenterDialogA23_10(DepotResultCenterDialogA23_9):
    """a23.10: structured evidence for systemID, completing the 21-control set."""

    def _a2310_render_system_id(self, parent, row: dict, item: dict) -> None:
        identity = row.get("archive_part") or {}
        system_id = (
            identity.get("system_id")
            or row.get("system_id")
            or item.get("value")
            or "–"
        )
        title = identity.get("title") or (
            "Alle arkivdeler" if row.get("is_all_archive_parts") else "–"
        )

        self._a232_card(parent, 0, "Identifikasjon", [
            ("Arkivdel", str(title)),
            ("systemID", str(system_id)),
            ("Kontrollstatus", str(item.get("control_status") or "–")),
            ("Kilde", str(item.get("source") or "arkivstruktur.xml")),
        ], columns=2)

        self._a232_card(parent, 1, "Kontekst", [
            ("Mapper", self._fmt_count(row.get("folder_count"))),
            ("Registreringer", self._fmt_count(row.get("registration_count"))),
            ("Journalposter", self._fmt_count(row.get("journalpost_count"))),
            ("Dokumentbeskrivelser", self._fmt_count(row.get("document_description_count"))),
            ("Dokumentobjekter", self._fmt_count(row.get("document_object_count"))),
        ], columns=2)

        self._a233_support_note(parent, 2, "Vurderingsstøtte", [
            "systemID vises direkte fra det materialiserte arkivdelgrunnlaget.",
            "Kontrollen brukes for å bekrefte identiteten til valgt arkivdel og skille den fra øvrige arkivdeler i uttrekket.",
            "Faglig behandling endrer ikke systemID eller andre kildeverdier.",
        ])

    def _a232_render_evidence(self, parent, index: int, item: dict) -> None:
        label = str(item.get("label") or "")
        parts = getattr(self, "_archive_parts", None) or []
        if label == "systemID" and 0 <= index < len(parts):
            self._a232_clear(parent)
            self._a2310_render_system_id(parent, parts[index], item)
            return
        return super()._a232_render_evidence(parent, index, item)
