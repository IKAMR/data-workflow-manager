from __future__ import annotations

from .depot_result_center_a23_11 import DepotResultCenterDialogA23_11


class DepotResultCenterDialogA23_12(DepotResultCenterDialogA23_11):
    """a23.12: make default 'Alle arkivdeler' use the same systemID table as subsets."""

    def _a2312_concrete_archive_parts(self) -> list[dict]:
        parts = getattr(self, "_archive_parts", None) or []
        concrete = []
        for row in parts:
            if row.get("is_all_archive_parts") or row.get("is_virtual_selection"):
                continue
            identity = row.get("archive_part") or {}
            # Concrete archive-part rows carry the archive-part identity.
            # Do not require a systemID here: missing IDs must remain visible
            # so the integrity summary can report them.
            if identity or row.get("system_id"):
                concrete.append(row)
        return concrete

    def _a2311_scope_rows(self, index: int) -> list[dict]:
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)):
            return []

        row = parts[index]

        if row.get("is_all_archive_parts"):
            return self._a2312_concrete_archive_parts()

        if row.get("is_virtual_selection"):
            selected = sorted(getattr(self, "_a171_selected", set()) or set())
            rows = []
            for pos in selected:
                if 0 <= pos < len(parts):
                    selected_row = parts[pos]
                    if selected_row.get("is_all_archive_parts") or selected_row.get("is_virtual_selection"):
                        continue
                    rows.append(selected_row)
            return rows

        return [row]

    def _a2311_render_system_id(self, parent, index: int, row: dict, item: dict) -> None:
        scope_rows = self._a2311_scope_rows(index)

        # The aggregate "Alle arkivdeler" row must always use the table view,
        # even if an unusual extraction contains only one concrete archive part.
        if row.get("is_all_archive_parts"):
            total, missing, duplicates = self._a2311_systemid_summary(scope_rows)
            self._a232_card(parent, 0, "Kontrollgrunnlag", [
                ("Utvalg", "Alle arkivdeler"),
                ("Arkivdeler", self._fmt_count(total)),
                ("Manglende systemID", self._fmt_count(missing)),
                ("Dupliserte systemID", self._fmt_count(duplicates)),
                ("Kontrollstatus", str(item.get("control_status") or "–")),
                ("Kilde", "arkivstruktur.xml"),
            ], columns=2)

            self._a2311_render_system_table(parent, scope_rows)

            notes = [
                "systemID vurderes per arkivdel og skal derfor ikke summeres eller slås sammen til én verdi.",
                "Tabellen viser arkivdel og systemID én rad per arkivdel i hele uttrekket.",
            ]
            if missing:
                notes.append(f"{missing} arkivdel(er) mangler systemID og bør vurderes.")
            if duplicates:
                notes.append(f"{duplicates} duplikatforekomst(er) av systemID er funnet og bør vurderes.")
            if not missing and not duplicates:
                notes.append("Alle arkivdeler har systemID, og ingen duplikater er funnet.")
            notes.append("Visningen bruker materialisert kontrollgrunnlag og kjører ingen ny analyse.")
            self._a233_support_note(parent, 2, "Vurderingsstøtte", notes)
            return

        return super()._a2311_render_system_id(parent, index, row, item)
