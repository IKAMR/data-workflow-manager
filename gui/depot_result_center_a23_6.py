from __future__ import annotations

from .depot_result_center_a23_5 import DepotResultCenterDialogA23_5


class DepotResultCenterDialogA23_6(DepotResultCenterDialogA23_5):
    """a23.6: structured evidence for the six central quantity controls."""

    _A236_COUNT_CONTROLS = {
        "Mapper": ("folders", "folder_count", "Mapper"),
        "Saker (saksmappe)": ("folders", "case_count", "Saker"),
        "Registreringer": ("registrations", "registration_count", "Registreringer"),
        "Journalposter": ("journalposts", "journalpost_count", "Journalposter"),
        "Dokumentbeskrivelser": ("objects", "document_description_count", "Dokumentbeskrivelser"),
        "Dokumentobjekter": ("objects", "document_object_count", "Dokumentobjekter"),
    }

    @staticmethod
    def _a236_pick_count(values: dict, row: dict, key: str, fallback=None):
        candidates = [
            values.get(key) if isinstance(values, dict) else None,
            row.get(key) if isinstance(row, dict) else None,
            fallback,
        ]
        # A few older materializations used synonymous count keys.
        aliases = {
            "case_count": ("sak_count", "saksmappe_count"),
            "document_description_count": ("description_count",),
            "document_object_count": ("object_count",),
        }
        for alias in aliases.get(key, ()):
            if isinstance(values, dict):
                candidates.append(values.get(alias))
            if isinstance(row, dict):
                candidates.append(row.get(alias))
        for value in candidates:
            if value not in (None, ""):
                return value
        return None

    def _a236_render_count_control(self, parent, row: dict, item: dict) -> None:
        label = str(item.get("label") or "")
        kind, key, display = self._A236_COUNT_CONTROLS[label]
        values = self._values_for_row(kind, row)
        count = self._a236_pick_count(values, row, key, item.get("value"))

        self._a232_card(parent, 0, "Kontrollresultat", [
            (display, self._fmt_count(count) if count is not None else "–"),
            ("Kontrollstatus", str(item.get("control_status") or "–")),
            ("Kilde", str(item.get("source") or "–")),
            ("Materialisert verdi", str(item.get("value") or "–")),
        ], columns=2)

        self._a232_card(parent, 1, "Kontekst i valgt arkivdel", [
            ("Mapper", self._fmt_count(row.get("folder_count"))),
            ("Registreringer", self._fmt_count(row.get("registration_count"))),
            ("Journalposter", self._fmt_count(row.get("journalpost_count"))),
            ("Dokumentbeskrivelser", self._fmt_count(row.get("document_description_count"))),
            ("Dokumentobjekter", self._fmt_count(row.get("document_object_count"))),
        ], columns=2)

        self._a233_support_note(parent, 2, "Vurderingsstøtte", [
            f"Kontrollen viser materialisert antall for {display.lower()} i valgt arkivdel.",
            "Kontekstkortet gjør det mulig å se tallet sammen med de andre hovedmengdene uten å bytte kontroll.",
            "Visningen kjører ingen ny analyse og endrer ikke det materialiserte kontrollgrunnlaget.",
        ])

    def _a232_render_evidence(self, parent, index: int, item: dict) -> None:
        label = str(item.get("label") or "")
        parts = getattr(self, "_archive_parts", None) or []
        if label in self._A236_COUNT_CONTROLS and 0 <= index < len(parts):
            self._a232_clear(parent)
            self._a236_render_count_control(parent, parts[index], item)
            return
        return super()._a232_render_evidence(parent, index, item)
