from __future__ import annotations

from .depot_result_center_a23_7 import DepotResultCenterDialogA23_7


class DepotResultCenterDialogA23_8(DepotResultCenterDialogA23_7):
    """a23.8: structured evidence for screening and disposal controls."""

    _A238_COUNT_CONTROLS = {
        "Skjerminger": ("screening_count", "Skjerminger", "kdrs.f08"),
        "Kassasjonsvedtak": ("disposal_decision_count", "Kassasjonsvedtak", "kdrs.f10"),
        "Utført kassasjon": ("performed_disposal_count", "Utført kassasjon", "kdrs.f11"),
        "Slettinger": ("deletion_count", "Slettinger", "kdrs.f13"),
    }

    def _a238_render_preservation_control(self, parent, row: dict, item: dict) -> None:
        label = str(item.get("label") or "")
        field, display, source = self._A238_COUNT_CONTROLS[label]
        value = row.get(field)

        self._a232_card(parent, 0, "Kontrollresultat", [
            (display, self._fmt_count(value)),
            ("Kontrollstatus", str(item.get("control_status") or "–")),
            ("Kilde", str(item.get("source") or source)),
            ("Materialisert verdi", str(item.get("value") or "–")),
        ], columns=2)

        context = [
            ("Skjerminger", self._fmt_count(row.get("screening_count"))),
            ("Kassasjonsvedtak", self._fmt_count(row.get("disposal_decision_count"))),
            ("Utført kassasjon", self._fmt_count(row.get("performed_disposal_count"))),
            ("Slettinger", self._fmt_count(row.get("deletion_count"))),
        ]
        self._a232_card(parent, 1, "Bevaring, skjerming og kassasjon – kontekst", context, columns=2)

        note_by_label = {
            "Skjerminger": [
                "Viser antall materialiserte skjermingsforekomster i valgt arkivdel.",
                "Tallet bør vurderes sammen med arkivdelens innhold og eventuell kjent skjermingspraksis.",
            ],
            "Kassasjonsvedtak": [
                "Viser antall materialiserte kassasjonsvedtak i valgt arkivdel.",
                "Forekomster kan vurderes mot forventet bevarings- og kassasjonspraksis.",
            ],
            "Utført kassasjon": [
                "Viser materialiserte forekomster av utført kassasjon.",
                "Kontrollen skiller utført kassasjon fra selve kassasjonsvedtaket.",
            ],
            "Slettinger": [
                "Viser materialiserte slettingsforekomster i valgt arkivdel.",
                "Slettinger bør behandles særskilt dersom de krever forklaring i depotvurderingen.",
            ],
        }
        notes = list(note_by_label.get(label, []))
        notes.append("Visningen kjører ingen ny analyse og endrer ikke kildedata eller materialiserte resultater.")
        self._a233_support_note(parent, 2, "Vurderingsstøtte", notes)

    def _a232_render_evidence(self, parent, index: int, item: dict) -> None:
        label = str(item.get("label") or "")
        parts = getattr(self, "_archive_parts", None) or []
        if label in self._A238_COUNT_CONTROLS and 0 <= index < len(parts):
            self._a232_clear(parent)
            self._a238_render_preservation_control(parent, parts[index], item)
            return
        return super()._a232_render_evidence(parent, index, item)
