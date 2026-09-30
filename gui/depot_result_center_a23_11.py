from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a23_10 import DepotResultCenterDialogA23_10


class DepotResultCenterDialogA23_11(DepotResultCenterDialogA23_10):
    """a23.11: scope-aware systemID evidence for one, many and all archive parts."""

    def _a2311_scope_rows(self, index: int) -> list[dict]:
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)):
            return []

        row = parts[index]

        if row.get("is_all_archive_parts"):
            return [
                item
                for item in parts
                if not item.get("is_all_archive_parts")
                and not item.get("is_virtual_selection")
            ]

        if row.get("is_virtual_selection"):
            selected = sorted(getattr(self, "_a171_selected", set()) or set())
            rows = []
            for pos in selected:
                if 0 <= pos < len(parts):
                    item = parts[pos]
                    if not item.get("is_all_archive_parts") and not item.get("is_virtual_selection"):
                        rows.append(item)
            return rows

        return [row]

    @staticmethod
    def _a2311_identity(row: dict) -> tuple[str, str]:
        identity = row.get("archive_part") or {}
        title = str(identity.get("title") or "–")
        system_id = str(identity.get("system_id") or "").strip()
        return title, system_id

    def _a2311_render_system_table(self, parent, rows: list[dict]) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color=theme.CARD_BG,
            border_width=1,
            border_color=theme.CARD_BORDER,
        )
        card.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Arkivdeler og systemID",
            anchor="w",
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(9, 6))

        table = ctk.CTkFrame(card, fg_color="transparent")
        table.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        table.grid_columnconfigure(0, weight=1)
        table.grid_columnconfigure(1, weight=1)

        for col, heading in enumerate(("Arkivdel", "systemID")):
            ctk.CTkLabel(
                table,
                text=heading,
                anchor="w",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=0, column=col, sticky="ew", padx=(0, 12 if col == 0 else 0), pady=(0, 4))

        for ridx, scope_row in enumerate(rows, start=1):
            title, system_id = self._a2311_identity(scope_row)
            ctk.CTkLabel(
                table,
                text=title,
                anchor="w",
                justify="left",
                wraplength=420,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=ridx, column=0, sticky="ew", padx=(0, 12), pady=2)
            ctk.CTkLabel(
                table,
                text=system_id or "Mangler",
                anchor="w",
                justify="left",
                wraplength=520,
                text_color=theme.TEXT_MAIN if system_id else theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=ridx, column=1, sticky="ew", pady=2)

    def _a2311_systemid_summary(self, rows: list[dict]) -> tuple[int, int, int]:
        ids = []
        missing = 0
        for row in rows:
            _title, system_id = self._a2311_identity(row)
            if system_id:
                ids.append(system_id)
            else:
                missing += 1
        duplicates = len(ids) - len(set(ids))
        return len(rows), missing, duplicates

    def _a2311_render_system_id(self, parent, index: int, row: dict, item: dict) -> None:
        scope_rows = self._a2311_scope_rows(index)
        total, missing, duplicates = self._a2311_systemid_summary(scope_rows)

        if len(scope_rows) <= 1:
            return super()._a2310_render_system_id(parent, row, item)

        scope_label = "Alle arkivdeler" if row.get("is_all_archive_parts") else f"{total} valgte arkivdeler"
        self._a232_card(parent, 0, "Kontrollgrunnlag", [
            ("Utvalg", scope_label),
            ("Arkivdeler", self._fmt_count(total)),
            ("Manglende systemID", self._fmt_count(missing)),
            ("Dupliserte systemID", self._fmt_count(duplicates)),
            ("Kontrollstatus", str(item.get("control_status") or "–")),
            ("Kilde", "arkivstruktur.xml"),
        ], columns=2)

        self._a2311_render_system_table(parent, scope_rows)

        notes = [
            "systemID vurderes per arkivdel og skal derfor ikke summeres eller slås sammen til én verdi.",
            "Tabellen viser arkivdel og systemID én rad per arkivdel i gjeldende utvalg.",
        ]
        if missing:
            notes.append(f"{missing} arkivdel(er) mangler systemID og bør vurderes.")
        if duplicates:
            notes.append(f"{duplicates} duplikatforekomst(er) av systemID er funnet i utvalget og bør vurderes.")
        if not missing and not duplicates:
            notes.append("Alle viste arkivdeler har systemID, og ingen duplikater er funnet i utvalget.")
        notes.append("Visningen bruker materialisert kontrollgrunnlag og kjører ingen ny analyse.")
        self._a233_support_note(parent, 2, "Vurderingsstøtte", notes)

    def _a232_render_evidence(self, parent, index: int, item: dict) -> None:
        label = str(item.get("label") or "")
        parts = getattr(self, "_archive_parts", None) or []
        if label == "systemID" and 0 <= index < len(parts):
            self._a232_clear(parent)
            self._a2311_render_system_id(parent, index, parts[index], item)
            return
        return super()._a232_render_evidence(parent, index, item)
