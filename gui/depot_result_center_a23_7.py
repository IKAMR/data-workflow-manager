from __future__ import annotations

from .depot_result_center_a23_6 import DepotResultCenterDialogA23_6


class DepotResultCenterDialogA23_7(DepotResultCenterDialogA23_6):
    """a23.7: structured evidence for document relation/type/version controls."""

    @staticmethod
    def _a237_first_counter(values: dict, *keys: str) -> dict:
        for key in keys:
            candidate = values.get(key)
            if isinstance(candidate, dict):
                return candidate
        return {}

    def _a237_render_distribution_control(
        self,
        parent,
        row: dict,
        item: dict,
        *,
        kind: str,
        keys: tuple[str, ...],
        total_label: str,
        total_key: str,
        title: str,
        support_lines: list[str],
    ) -> None:
        values = self._values_for_row(kind, row)
        counter = self._a237_first_counter(values, *keys)
        rows = self._a231_counter_rows(counter, limit=100)

        total = values.get(total_key, row.get(total_key))
        self._a232_card(parent, 0, "Kontrollgrunnlag", [
            (total_label, self._fmt_count(total)),
            ("Kontrollstatus", str(item.get("control_status") or "–")),
            ("Kilde", str(item.get("source") or "–")),
            ("Registrerte verdier", self._fmt_count(len(rows))),
        ], columns=2)

        self._a233_distribution(parent, 1, title, rows, limit=18)

        notes = list(support_lines)
        notes.append("Tallene leses fra materialisert kontrollgrunnlag; visningen kjører ingen ny analyse.")
        self._a233_support_note(parent, 2, "Vurderingsstøtte", notes)

    def _a237_render_relation_type(self, parent, row: dict, item: dict) -> None:
        self._a237_render_distribution_control(
            parent,
            row,
            item,
            kind="descriptions",
            keys=("relation_type_counts", "relation_counts", "tilknytning_counts"),
            total_label="Dokumentbeskrivelser totalt",
            total_key="document_description_count",
            title="Tilknytning til registrering – materialisert fordeling",
            support_lines=[
                "Fordelingen viser hvordan dokumentbeskrivelser er knyttet til registreringer i valgt arkivdel.",
                "Uventede eller sjeldne relasjonstyper kan dokumenteres direkte i den faglige vurderingen.",
            ],
        )

    def _a237_render_document_type(self, parent, row: dict, item: dict) -> None:
        self._a237_render_distribution_control(
            parent,
            row,
            item,
            kind="descriptions",
            keys=("document_type_counts", "type_counts"),
            total_label="Dokumentbeskrivelser totalt",
            total_key="document_description_count",
            title="Dokumenttype – materialisert fordeling",
            support_lines=[
                "Fordelingen viser hvilke dokumenttyper som faktisk forekommer i valgt arkivdel.",
                "Visningen gjør det enklere å identifisere avvikende eller uventede dokumenttyper.",
            ],
        )

    def _a237_render_variant_format(self, parent, row: dict, item: dict) -> None:
        self._a237_render_distribution_control(
            parent,
            row,
            item,
            kind="objects",
            keys=("variant_format_counts", "variant_counts"),
            total_label="Dokumentobjekter totalt",
            total_key="document_object_count",
            title="Variantformat – materialisert fordeling",
            support_lines=[
                "Fordelingen viser hvilke variantformater som forekommer blant dokumentobjektene.",
                "Variantformat kan vurderes sammen med filformat og versjonsnummer for samme arkivdel.",
            ],
        )

    def _a237_render_version_number(self, parent, row: dict, item: dict) -> None:
        self._a237_render_distribution_control(
            parent,
            row,
            item,
            kind="objects",
            keys=("version_number_counts", "version_counts"),
            total_label="Dokumentobjekter totalt",
            total_key="document_object_count",
            title="Versjonsnummer – materialisert fordeling",
            support_lines=[
                "Fordelingen viser hvilke versjonsnumre som er registrert på dokumentobjektene.",
                "Uvanlige versjonsmønstre kan behandles som et faglig vurderingspunkt uten å endre kildedata.",
            ],
        )

    def _a232_render_evidence(self, parent, index: int, item: dict) -> None:
        label = str(item.get("label") or "")
        parts = getattr(self, "_archive_parts", None) or []
        if 0 <= index < len(parts):
            row = parts[index]
            if label == "Tilknytning til registrering":
                self._a232_clear(parent)
                self._a237_render_relation_type(parent, row, item)
                return
            if label == "Dokumenttype":
                self._a232_clear(parent)
                self._a237_render_document_type(parent, row, item)
                return
            if label == "Variantformat":
                self._a232_clear(parent)
                self._a237_render_variant_format(parent, row, item)
                return
            if label == "Versjonsnummer":
                self._a232_clear(parent)
                self._a237_render_version_number(parent, row, item)
                return
        return super()._a232_render_evidence(parent, index, item)
