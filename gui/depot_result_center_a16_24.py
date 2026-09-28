from __future__ import annotations

import json
from pathlib import Path

from .depot_result_center_a16_23 import DepotResultCenterDialogA16_23


class DepotResultCenterDialogA16_24(DepotResultCenterDialogA16_23):
    """a16.24: paired archive-part KPIs plus folder/registration type breakdowns."""

    def __init__(self, master, **kwargs) -> None:
        self._a1624_types_loaded = False
        self._a1624_folder_types_total: dict[str, int] = {}
        self._a1624_registration_types_total: dict[str, int] = {}
        self._a1624_folder_types_by_part: dict[str, dict[str, int]] = {}
        self._a1624_registration_types_by_part: dict[str, dict[str, int]] = {}
        self._a1624_folder_unspecialized_total = None
        self._a1624_registration_unspecialized_total = None
        self._a1624_folder_unspecialized_by_part: dict[str, int] = {}
        self._a1624_registration_unspecialized_by_part: dict[str, int] = {}
        super().__init__(master, **kwargs)
        self._rename_pair_headings()
        if getattr(self, "_archive_parts", None):
            self._show_archive_part(getattr(self, "_archive_index", 0))

    @staticmethod
    def _normalise_counter(value) -> dict[str, int]:
        if not isinstance(value, dict):
            return {}
        result: dict[str, int] = {}
        for key, count in value.items():
            label = str(key).strip() or "Uten type"
            try:
                result[label] = int(count)
            except (TypeError, ValueError):
                continue
        return result

    @staticmethod
    def _as_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _load_type_counts(self) -> None:
        if self._a1624_types_loaded:
            return
        self._a1624_types_loaded = True

        evidence = self.model.get("evidence") or {}
        xpath_run = str(evidence.get("source_xpath_run") or "").strip()
        if not xpath_run:
            return

        def load_one(filename: str):
            path = Path(xpath_run) / "results" / filename
            if not path.is_file():
                return {}
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}

        c13 = load_one("kdrs_c13.json")
        c14 = load_one("kdrs_c14.json")

        values13 = c13.get("values") or {}
        values14 = c14.get("values") or {}
        self._a1624_folder_types_total = self._normalise_counter(values13.get("type_counts"))
        self._a1624_registration_types_total = self._normalise_counter(values14.get("type_counts"))
        self._a1624_folder_unspecialized_total = self._as_int(values13.get("without_specialization"))
        self._a1624_registration_unspecialized_total = self._as_int(values14.get("without_specialization"))

        for item in values13.get("_archive_parts") or []:
            identity = item.get("archive_part") or {}
            system_id = str(identity.get("system_id") or "").strip()
            if not system_id:
                continue
            vals = item.get("values") or {}
            self._a1624_folder_types_by_part[system_id] = self._normalise_counter(vals.get("type_counts"))
            n = self._as_int(vals.get("without_specialization"))
            if n is not None:
                self._a1624_folder_unspecialized_by_part[system_id] = n

        for item in values14.get("_archive_parts") or []:
            identity = item.get("archive_part") or {}
            system_id = str(identity.get("system_id") or "").strip()
            if not system_id:
                continue
            vals = item.get("values") or {}
            self._a1624_registration_types_by_part[system_id] = self._normalise_counter(vals.get("type_counts"))
            n = self._as_int(vals.get("without_specialization"))
            if n is not None:
                self._a1624_registration_unspecialized_by_part[system_id] = n

    def _type_data_for_row(self, row: dict):
        self._load_type_counts()
        if row.get("is_all_archive_parts"):
            return (
                self._a1624_folder_types_total,
                self._a1624_registration_types_total,
                self._a1624_folder_unspecialized_total,
                self._a1624_registration_unspecialized_total,
            )
        identity = row.get("archive_part") or {}
        system_id = str(identity.get("system_id") or "").strip()
        return (
            self._a1624_folder_types_by_part.get(system_id, {}),
            self._a1624_registration_types_by_part.get(system_id, {}),
            self._a1624_folder_unspecialized_by_part.get(system_id),
            self._a1624_registration_unspecialized_by_part.get(system_id),
        )

    @staticmethod
    def _counter_get(counter: dict[str, int], wanted: str) -> int | None:
        wanted_cf = wanted.casefold()
        for key, value in counter.items():
            if key.casefold() == wanted_cf:
                return value
        return None

    def _rename_pair_headings(self) -> None:
        """Use full 'journalposter' wording in the three archive summary cards."""
        values = getattr(self, "_a1618_pair_values", None) or {}
        for (left, right), value_widget in values.items():
            if left == "registration_count" and right == "journalpost_count":
                try:
                    for child in value_widget.master.winfo_children():
                        if child is not value_widget:
                            child.configure(text="Registreringer / journalposter")
                except Exception:
                    pass

    def _refresh_pair_kpis(self, index: int) -> None:
        """Fill the inherited Mapper/saker card with the real materialized case count."""
        values = getattr(self, "_a1618_pair_values", None) or {}
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)):
            return
        row = parts[index]
        for (left, right), label in values.items():
            left_value = row.get(left)
            if left == "folder_count" and right == "case_folder_count":
                right_value = self._case_count_for_row(row)
            else:
                right_value = row.get(right)
            label.configure(
                text=f"{self._fmt_count(left_value)} / {self._fmt_count(right_value)}"
            )

    def _render_a10_archive_part(self, index: int) -> None:
        super()._render_a10_archive_part(index)
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)) or not hasattr(self, "_a10_content"):
            return

        row = parts[index]
        folder_types, reg_types, folder_unspec, reg_unspec = self._type_data_for_row(row)

        folder_total = self._as_int(row.get("folder_count"))
        case_count = self._as_int(self._case_count_for_row(row))
        reg_total = self._as_int(row.get("registration_count"))
        journal_count = self._as_int(row.get("journalpost_count"))

        other_folders = None if folder_total is None or case_count is None else max(0, folder_total - case_count)
        other_regs = None if reg_total is None or journal_count is None else max(0, reg_total - journal_count)

        lines = [
            f"Mapper: {self._fmt_count(folder_total)}",
            f"Saker: {self._fmt_count(case_count)}",
            f"Andre mapper: {self._fmt_count(other_folders)}",
        ]

        for type_name, count in sorted(folder_types.items(), key=lambda item: (-item[1], item[0].casefold())):
            if type_name.casefold() == "saksmappe":
                continue
            lines.append(f"  {type_name}: {self._fmt_count(count)}")
        if folder_unspec not in (None, 0) and not any(k.casefold() == "uten type" for k in folder_types):
            lines.append(f"  Uten spesialisering: {self._fmt_count(folder_unspec)}")

        lines.extend((
            "",
            f"Registreringer: {self._fmt_count(reg_total)}",
            f"Journalposter: {self._fmt_count(journal_count)}",
            f"Andre registreringer: {self._fmt_count(other_regs)}",
        ))
        for type_name, count in sorted(reg_types.items(), key=lambda item: (-item[1], item[0].casefold())):
            if type_name.casefold() == "journalpost":
                continue
            lines.append(f"  {type_name}: {self._fmt_count(count)}")
        if reg_unspec not in (None, 0) and not any(k.casefold() == "uten type" for k in reg_types):
            lines.append(f"  Uten spesialisering: {self._fmt_count(reg_unspec)}")

        lines.extend((
            "",
            f"Dokumentbeskrivelser: {self._fmt_count(row.get('document_description_count'))}",
            f"Dokumentobjekter: {self._fmt_count(row.get('document_object_count'))}",
            f"Skjerminger: {self._fmt_count(row.get('screening_count'))}",
            f"Kassasjonsvedtak: {self._fmt_count(row.get('disposal_decision_count'))}",
            f"Utført kassasjon: {self._fmt_count(row.get('performed_disposal_count'))}",
            f"Slettinger: {self._fmt_count(row.get('deletion_count'))}",
        ))
        self._a10_content.configure(text="\n".join(lines))
