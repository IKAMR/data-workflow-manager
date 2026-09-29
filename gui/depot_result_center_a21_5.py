from __future__ import annotations

import re

import customtkinter as ctk

from . import theme
from .depot_result_center_a21_4 import DepotResultCenterDialogA21_4


class DepotResultCenterDialogA21_5(DepotResultCenterDialogA21_4):
    """a21.5: aligned extraction period rows and compact PRONOM columns.

    Arkivdeler is deliberately unchanged in this step.  The changes are limited
    to the extraction overview period card and the Filformater/PRONOM table.
    """

    _FORMAT_REPLACEMENTS = (
        ("Portable Document Format", "PDF"),
        ("Exchangeable Image File Format", "EXIF"),
        ("Graphics Interchange Format", "GIF"),
        ("Tagged Image File Format", "TIFF"),
        ("Portable Network Graphics", "PNG"),
        ("Hypertext Markup Language", "HTML"),
        ("Extensible Markup Language", "XML"),
        ("Rich Text Format", "RTF"),
    )

    @classmethod
    def _a215_short_format_name(cls, value: object, max_chars: int = 64) -> str:
        """Shorten only for display while keeping the identifying parts.

        Known verbose generic phrases are compacted first.  If a PRONOM name is
        still extreme, preserve both the beginning and the distinguishing tail.
        The underlying materialized value is never changed.
        """
        text = re.sub(r"\s+", " ", str(value or "–")).strip() or "–"
        for long_name, short_name in cls._FORMAT_REPLACEMENTS:
            text = text.replace(long_name, short_name)
        if len(text) <= max_chars:
            return text
        head = max(24, max_chars - 22)
        tail = max_chars - head - 3
        return f"{text[:head].rstrip()}...{text[-tail:].lstrip()}"

    def _a211_period_card(self, parent, column: int, period: dict[str, object]) -> None:
        """Render start/end years in stable columns for quick visual comparison."""
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER, corner_radius=7)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 5))
        card.grid_columnconfigure(0, weight=0, minsize=78)
        card.grid_columnconfigure(1, weight=0, minsize=48)
        card.grid_columnconfigure(2, weight=0, minsize=18)
        card.grid_columnconfigure(3, weight=0, minsize=48)
        card.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(
            card,
            text="Tidsprofil – hele uttrekket",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, columnspan=5, sticky="ew", padx=12, pady=(9, 4))

        rows = (
            ("Oppgitt", period.get("declared_start"), period.get("declared_end")),
            ("Observert", period.get("observed_start"), period.get("observed_end")),
            ("Vurdert", period.get("reviewed_start"), period.get("reviewed_end")),
        )
        for row_no, (label, start, end) in enumerate(rows, start=1):
            ctk.CTkLabel(
                card, text=label, anchor="w", text_color=theme.TEXT_SUB,
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=row_no, column=0, sticky="w", padx=(12, 4), pady=0)
            ctk.CTkLabel(
                card, text=str(start if start is not None else "–"), anchor="e",
                text_color=theme.TEXT_SUB, font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=row_no, column=1, sticky="e", pady=0)
            ctk.CTkLabel(
                card, text="–", anchor="center", text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=row_no, column=2, sticky="ew", pady=0)
            ctk.CTkLabel(
                card, text=str(end if end is not None else "–"), anchor="w",
                text_color=theme.TEXT_SUB, font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=row_no, column=3, sticky="w", pady=0)

        outliers = period.get("outliers") or []
        note = "Ingen materialiserte årspunkter utenfor hovedbildet."
        if outliers:
            shown = ", ".join(str(y) for y in outliers[:5])
            if len(outliers) > 5:
                shown += " …"
            note = f"År som bør ses nærmere på: {shown}"
        ctk.CTkLabel(
            card,
            text=note,
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=4, column=0, columnspan=5, sticky="ew", padx=12, pady=(4, 8))

    def _replace_pronom_text_with_table(self, tab) -> None:
        """Keep PRONOM columns grouped from the left and scrollbar at far right."""
        old = getattr(self, "_a14_pronom_text", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass

        for col in range(10):
            try:
                tab.grid_columnconfigure(col, weight=0, minsize=0)
            except Exception:
                pass
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        panel = ctk.CTkFrame(tab, fg_color="transparent")
        panel.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        arkade = ((self.model.get("external_validation") or {}).get("arkade5") or {})
        summary = arkade.get("pronom_summary") or {}
        imports = list(arkade.get("imports") or [])

        ctk.CTkLabel(
            panel,
            text=(
                f"Statistikksett: {summary.get('statistics_imports', 0)}   |   "
                f"Rader: {summary.get('statistics_rows', 0)}   |   "
                f"Filer: {summary.get('total_files', 0)}   |   "
                f"Unike Format-ID: {summary.get('unique_format_ids', 0)}"
            ),
            anchor="w",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        table = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        table.grid(row=1, column=0, sticky="nsew")

        # Data columns stay grouped from the left.  Only the final spacer grows,
        # so a long Filtype can never push Formatversjon/RAF/Antall to the edge.
        widths = (125, 520, 145, 120, 95)
        for col, width in enumerate(widths):
            table.grid_columnconfigure(col, weight=0, minsize=width)
        table.grid_columnconfigure(5, weight=1, minsize=12)

        headers = ("Format-ID / PUID", "Filtype", "Formatversjon", "RAF-220301", "Antall")
        for col, heading in enumerate(headers):
            ctk.CTkLabel(
                table,
                text=heading,
                anchor="w",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=0, column=col, sticky="w", padx=6, pady=(4, 7))

        row_no = 1
        for item in imports:
            pronom = item.get("pronom") or {}
            if not pronom.get("available"):
                continue
            stats = pronom.get("statistics") or {}
            for data in list(stats.get("rows") or []):
                values = (
                    data.get("format_id") or "–",
                    self._a215_short_format_name(data.get("file_type")),
                    data.get("format_version") or "–",
                    data.get("raf_220301") or "–",
                    data.get("count") if data.get("count") is not None else "–",
                )
                for col, value in enumerate(values):
                    ctk.CTkLabel(
                        table,
                        text=str(value),
                        anchor="w",
                        justify="left",
                        font=theme.font(theme.SMALL_SIZE),
                    ).grid(row=row_no, column=col, sticky="w", padx=6, pady=2)
                row_no += 1

        if row_no == 1:
            ctk.CTkLabel(
                table,
                text="Ingen PRONOM-statistikk er materialisert i depotrapporten.",
                anchor="w",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, columnspan=5, sticky="ew", padx=6, pady=8)
