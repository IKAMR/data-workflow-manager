from __future__ import annotations

from .depot_result_center_a22_3 import DepotResultCenterDialogA22_3


class DepotResultCenterDialogA23_1(DepotResultCenterDialogA22_3):
    """a23.1: control-specific evidence for the first representative controls.

    The workspace still reads already materialized result data only.  No new
    XML/XPath analysis is started from the result view.
    """

    _A231_DEDICATED = {
        "Arkivdel",
        "Mappetyper",
        "Journalposttyper",
        "Format (metadata)",
    }

    @staticmethod
    def _a231_value(value, fallback="–") -> str:
        if value is None or value == "":
            return fallback
        return str(value)

    @staticmethod
    def _a231_counter_rows(values: dict | None, *, limit: int = 20) -> list[tuple[str, int]]:
        if not isinstance(values, dict):
            return []
        rows = []
        for key, value in values.items():
            if key == "_archive_parts" or isinstance(value, dict):
                continue
            try:
                number = int(value or 0)
            except (TypeError, ValueError):
                continue
            rows.append((str(key or "(ikke angitt)"), number))
        rows.sort(key=lambda row: (-row[1], row[0].casefold()))
        return rows[:limit]

    @staticmethod
    def _a231_table(title: str, rows: list[tuple[str, int]]) -> list[str]:
        lines = [title]
        if not rows:
            lines.append("  Ingen materialiserte fordelingsverdier.")
            return lines
        width = max(len(name) for name, _count in rows)
        width = min(max(width, 8), 42)
        total = sum(count for _name, count in rows)
        for name, count in rows:
            shown = name if len(name) <= width else name[: max(1, width - 1)] + "…"
            share = (count / total * 100.0) if total else 0.0
            lines.append(f"  {shown:<{width}}  {count:>10,}  {share:>6.1f} %".replace(",", " "))
        lines.append(f"  {'Sum':<{width}}  {total:>10,}".replace(",", " "))
        return lines

    def _a231_archive_part_evidence(self, index: int, row: dict, item: dict) -> str:
        identity = row.get("archive_part") or {}
        lines = [
            "ARKIVDEL – IDENTITET OG KONTROLLGRUNNLAG",
            "",
            f"Navn: {self._a231_value(identity.get('title'))}",
            f"Kortnavn: {self._a231_value(identity.get('short_name') or identity.get('shortName'))}",
            f"systemID: {self._a231_value(identity.get('system_id'))}",
        ]
        for key, label in (
            ("archive_period_start_date", "Oppgitt fra"),
            ("archive_period_end_date", "Oppgitt til"),
        ):
            if identity.get(key):
                lines.append(f"{label}: {identity.get(key)}")
        try:
            period = self._effective_period(row, index)
            if isinstance(period, (tuple, list)) and len(period) >= 2:
                lines.append(f"Observert periode: {period[0] or '–'}–{period[1] or '–'}")
            elif period:
                lines.append(f"Observert periode: {period}")
        except Exception:
            pass
        lines.extend([
            "",
            "OMFANG",
            f"Mapper: {self._fmt_count(row.get('folder_count'))}",
            f"Registreringer: {self._fmt_count(row.get('registration_count'))}",
            f"Journalposter: {self._fmt_count(row.get('journalpost_count'))}",
            f"Dokumentbeskrivelser: {self._fmt_count(row.get('document_description_count'))}",
            f"Dokumentobjekter: {self._fmt_count(row.get('document_object_count'))}",
            "",
            f"Kilde for kontrollen: {item.get('source') or '–'}",
        ])
        return "\n".join(lines)

    def _a231_folder_type_evidence(self, row: dict, item: dict) -> str:
        folder = self._values_for_row("folders", row)
        values = folder.get("type_counts") or folder.get("folder_type_counts") or {}
        rows = self._a231_counter_rows(values)
        lines = [
            "MAPPETYPER – FORDELING I VALGT ARKIVDEL",
            "",
            f"Mapper totalt: {self._fmt_count(folder.get('folder_count', row.get('folder_count')))}",
            f"Kilde: {item.get('source') or '–'}",
            "",
        ]
        lines.extend(self._a231_table("Materialiserte mappetyper", rows))
        lines.extend([
            "",
            "Vurderingsstøtte",
            "• Fordelingen viser hvilke mappetyper som faktisk forekommer i uttrekket.",
            "• Verdiene er materialisert fra eksisterende testresultater; visningen kjører ingen ny analyse.",
        ])
        return "\n".join(lines)

    def _a231_journalpost_type_evidence(self, row: dict, item: dict) -> str:
        journal = self._values_for_row("journalposts", row)
        values = journal.get("journalpost_type_counts") or {}
        rows = self._a231_counter_rows(values)
        lines = [
            "JOURNALPOSTTYPER – FORDELING I VALGT ARKIVDEL",
            "",
            f"Journalposter totalt: {self._fmt_count(journal.get('journalpost_count', row.get('journalpost_count')))}",
            f"Kilde: {item.get('source') or '–'}",
            "",
        ]
        lines.extend(self._a231_table("Materialiserte journalposttyper", rows))
        lines.extend([
            "",
            "Vurderingsstøtte",
            "• Bruk fordelingen til å kontrollere om registrerte journalposttyper er forståelige for arkivdelen.",
            "• Eventuelle avvik eller forklaringer registreres i Faglig vurdering til høyre.",
        ])
        return "\n".join(lines)

    def _a231_format_metadata_evidence(self, row: dict, item: dict) -> str:
        obj = self._values_for_row("objects", row)
        values = obj.get("format_counts") or {}
        rows = self._a231_counter_rows(values, limit=30)
        lines = [
            "FORMAT (METADATA) – VERDIER I DOKUMENTOBJEKT",
            "",
            f"Dokumentobjekter totalt: {self._fmt_count(obj.get('document_object_count', row.get('document_object_count')))}",
            f"Kontrollstatus: {item.get('control_status') or '–'}",
            f"Kilde: {item.get('source') or '–'}",
            "",
        ]
        lines.extend(self._a231_table("Materialiserte formatverdier", rows))
        lines.extend([
            "",
            "Vurderingsstøtte",
            "• Dette er metadatafeltet format fra uttrekket, ikke PRONOM-identifikasjonen av de fysiske filene.",
            "• Sammenligning mot filformat-/PRONOM-visningen gjøres senere som egen kontrollflate.",
        ])
        return "\n".join(lines)

    def _a223_context_text(self, index: int, item: dict) -> str:
        label = str(item.get("label") or "")
        parts = getattr(self, "_archive_parts", None) or []
        if label not in self._A231_DEDICATED or not (0 <= index < len(parts)):
            return super()._a223_context_text(index, item)

        row = parts[index]
        if label == "Arkivdel":
            return self._a231_archive_part_evidence(index, row, item)
        if label == "Mappetyper":
            return self._a231_folder_type_evidence(row, item)
        if label == "Journalposttyper":
            return self._a231_journalpost_type_evidence(row, item)
        if label == "Format (metadata)":
            return self._a231_format_metadata_evidence(row, item)
        return super()._a223_context_text(index, item)
