from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_12 import DepotResultCenterDialogA16_12


class DepotResultCenterDialogA16_13(DepotResultCenterDialogA16_12):
    """a16.13: materialized outer-year evidence for the aggregate archive view."""

    _SERIES_LABELS = (
        ("folder", "Mapper/saker"),
        ("journal", "Journalposter"),
        ("document_description", "Dok.beskr."),
        ("document_object", "Dok.objekter"),
    )

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if not getattr(self, "_archive_parts", None):
            return
        row = self._archive_parts[index]
        if not row.get("is_all_archive_parts"):
            return

        summary = self.model.get("all_archive_parts_summary") or {}
        periods = summary.get("observed_period_by_series") or {}
        findings = summary.get("cross_source_year_findings") or []
        period_text = getattr(self, "_a164_period_text", None)
        if period_text is None:
            return

        declared = summary.get("declared_period") or {}
        observed = summary.get("observed_period") or {}
        declared_text = f"{declared.get('start_date') or '–'} → {declared.get('end_date') or '–'}"
        observed_text = f"{observed.get('first_year') or '–'}–{observed.get('last_year') or '–'}"
        series_bits = []
        for key, label in self._SERIES_LABELS:
            value = periods.get(key) or {}
            series_bits.append(
                f"{label}: {value.get('first_year') or '–'}–{value.get('last_year') or '–'}"
            )
        lines = [
            f"Hele uttrekket oppgitt: {declared_text}   |   Samlet observert: {observed_text}",
            "   |   ".join(series_bits),
        ]
        if findings:
            years = ", ".join(str(item.get("year")) for item in findings if item.get("year"))
            lines.append(
                f"Krysskontroll år: {len(findings)} vurderingspunkt(er)" +
                (f" – {years}" if years else "")
            )
        else:
            lines.append("Krysskontroll år: ingen dokumentår uten mappe/journal-aktivitet.")
        period_text.configure(text="\n".join(lines))

    def _render_a166(self, index: int) -> None:
        super()._render_a166(index)
        if not self._archive_parts[index].get("is_all_archive_parts"):
            return
        table = getattr(self, "_a166_table", None)
        if table is None:
            return
        findings = {
            str(item.get("year")): item
            for item in (self.model.get("all_archive_parts_summary") or {}).get("cross_source_year_findings") or []
            if item.get("year")
        }
        if not findings:
            return
        # Mark materialized review years in the first column without changing counts.
        for child in table.winfo_children():
            try:
                info = child.grid_info()
                if int(info.get("column", -1)) != 0 or int(info.get("row", 0)) <= 0:
                    continue
                year = str(child.cget("text")).strip()
                if year in findings:
                    child.configure(
                        text=f"{year} !",
                        text_color=theme.TEXT_SUB,
                        font=theme.font(theme.SMALL_SIZE, weight="bold"),
                    )
            except Exception:
                pass
