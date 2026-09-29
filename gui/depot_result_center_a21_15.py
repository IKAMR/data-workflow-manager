from __future__ import annotations

import re
import tkinter as tk

import customtkinter as ctk

from . import theme
from .depot_result_center_a21_14 import DepotResultCenterDialogA21_14


class DepotResultCenterDialogA21_15(DepotResultCenterDialogA21_14):
    """a21.15: consistent format names, compact format table, larger local hover."""

    _PUID_FRIENDLY = {
        "fmt/354": "Acrobat PDF/A-1b",
        "fmt/95": "Acrobat PDF/A-1a",
        "fmt/477": "Acrobat PDF/A-2b",
        "fmt/480": "Acrobat PDF/A-3b",
        "fmt/476": "Acrobat PDF/A-2a",
        "fmt/479": "Acrobat PDF/A-3a",
        "fmt/412": "Microsoft Word (docx)",
        "fmt/40": "Microsoft Word (doc)",
        "fmt/214": "Microsoft Excel (xlsx)",
        "fmt/61": "Microsoft Excel (xls)",
    }

    @classmethod
    def _a2115_acrobat_name(cls, raw: str, version: str) -> str | None:
        text = " ".join(str(raw or "").split())
        upper = text.upper()
        clean_version = str(version or "").strip()

        if "PDF/A" in upper:
            if re.fullmatch(r"[123][ABU]?", clean_version, flags=re.I):
                return f"Acrobat PDF/A-{clean_version}"
            match = re.search(r"PDF/A\s*[-–—]?\s*([123][ABU]?)", text, flags=re.I)
            if match:
                return f"Acrobat PDF/A-{match.group(1)}"
            return "Acrobat PDF/A"

        if "PDF/X" in upper:
            match = re.search(r"EXCHANGE\s+(?:PDF/X-)?([^,;]+)$", text, flags=re.I)
            if match:
                suffix = match.group(1).strip(" -–—")
                if suffix:
                    return f"Acrobat PDF/X-{suffix}"
            match = re.search(r"PDF/X\s*[-–—]?\s*([^,;]+)$", text, flags=re.I)
            if match:
                suffix = match.group(1).strip(" -–—")
                if suffix and "Portable Document Format" not in suffix:
                    return f"Acrobat PDF/X-{suffix}"
            return "Acrobat PDF/X"

        if "PORTABLE DOCUMENT FORMAT" in upper or upper.startswith("ACROBAT PDF"):
            if clean_version and clean_version not in {"-", "–", "—"}:
                return f"Acrobat PDF {clean_version}"
            match = re.search(r"ACROBAT\s+PDF\s+([0-9]+(?:\.[0-9]+)?)", text, flags=re.I)
            if match:
                return f"Acrobat PDF {match.group(1)}"
            return "Acrobat PDF"

        return None

    @classmethod
    def _a2114_display_format_name(cls, row: dict) -> str:
        puid = str(row.get("format_id") or "").strip()
        version = str(row.get("format_version") or "").strip()
        raw = str(
            row.get("format_name")
            or row.get("name")
            or row.get("file_type")
            or row.get("format")
            or ""
        ).strip()

        acrobat = cls._a2115_acrobat_name(raw, version)
        if acrobat:
            return acrobat
        if puid in cls._PUID_FRIENDLY:
            return cls._PUID_FRIENDLY[puid]

        return cls._a215_short_format_name(raw or puid or "Ukjent format", max_chars=52)

    def _a211_formats_card(self, parent, column: int, formats, metrics) -> None:
        """Overview card with count | display name | right-aligned PUID."""
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER, corner_radius=7)
        card.grid(row=0, column=column, sticky="nsew", padx=5)
        card.grid_columnconfigure(0, weight=0, minsize=78)
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(2, weight=0, minsize=76)

        ctk.CTkLabel(
            card,
            text="Filformater",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(9, 4))

        if not formats:
            ctk.CTkLabel(
                card,
                text=(
                    f"{self._fmt_count(metrics.get('pronom_rows')):>9}  ·  PRONOM-statistikkrader\n"
                    "Ingen toppformater materialisert."
                ),
                anchor="nw",
                justify="left",
                text_color=theme.TEXT_SUB,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 8))
            return

        for row_no, (name, puid, count) in enumerate(formats, start=1):
            ctk.CTkLabel(
                card,
                text=self._fmt_count(count),
                anchor="e",
                text_color=theme.TEXT_SUB,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=row_no, column=0, sticky="ew", padx=(12, 8), pady=1)
            ctk.CTkLabel(
                card,
                text=name,
                anchor="w",
                text_color=theme.TEXT_SUB,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=row_no, column=1, sticky="ew", padx=(0, 8), pady=1)
            ctk.CTkLabel(
                card,
                text=f"({puid})" if puid else "",
                anchor="e",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=row_no, column=2, sticky="ew", padx=(4, 12), pady=1)

        ctk.CTkFrame(card, fg_color="transparent", height=5).grid(
            row=len(formats) + 1, column=0, columnspan=3, sticky="ew"
        )

    def _a2114_collect_pronom_rows(self) -> list[dict]:
        arkade = ((self.model.get("external_validation") or {}).get("arkade5") or {})
        rows: list[dict] = []
        for item in list(arkade.get("imports") or []):
            pronom = item.get("pronom") or {}
            if not pronom.get("available"):
                continue
            stats = pronom.get("statistics") or {}
            for raw in list(stats.get("rows") or []):
                try:
                    count = int(raw.get("count") or 0)
                except (TypeError, ValueError):
                    count = 0
                rows.append({
                    "format_id": str(raw.get("format_id") or "–"),
                    "file_type": self._a2114_display_format_name(raw),
                    "archive_format": str(raw.get("raf_220301") or "–"),
                    "count": count,
                })
        return rows

    def _replace_pronom_text_with_table(self, tab) -> None:
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
        panel.grid_rowconfigure(3, weight=1)

        arkade = ((self.model.get("external_validation") or {}).get("arkade5") or {})
        summary = arkade.get("pronom_summary") or {}
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
        ).grid(row=0, column=0, sticky="ew", pady=(0, 3))

        ctk.CTkLabel(
            panel,
            text="Arkivformatstatus viser Gyldig / Ikke gyldig fra RAF-220301 i importert Arkade 5-statistikk.",
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", pady=(0, 6))

        headers = ctk.CTkFrame(panel, fg_color="transparent")
        headers.grid(row=2, column=0, sticky="ew")
        table = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        table.grid(row=3, column=0, sticky="nsew")

        widths = (430, 140, 180, 110)
        for holder in (headers, table):
            for col, width in enumerate(widths):
                holder.grid_columnconfigure(col, weight=0, minsize=width)
            holder.grid_columnconfigure(4, weight=1, minsize=12)

        columns = (
            ("file_type", "Filformat"),
            ("format_id", "PUID"),
            ("archive_format", "Arkivformatstatus"),
            ("count", "Antall"),
        )
        rows = self._a2114_collect_pronom_rows()
        state = {"key": "count", "reverse": True}
        header_buttons = {}

        def clear_table():
            for child in table.winfo_children():
                try:
                    child.destroy()
                except Exception:
                    pass

        def refresh_headers():
            for key, title in columns:
                marker = ""
                if state["key"] == key:
                    marker = " ▼" if state["reverse"] else " ▲"
                try:
                    header_buttons[key].configure(text=title + marker)
                except Exception:
                    pass

        def render():
            clear_table()
            ordered = sorted(
                rows,
                key=lambda row: self._a2114_sort_value(row, state["key"]),
                reverse=state["reverse"],
            )
            refresh_headers()
            if not ordered:
                ctk.CTkLabel(
                    table,
                    text="Ingen PRONOM-statistikk er materialisert i depotrapporten.",
                    anchor="w",
                    text_color=theme.TEXT_MUTED,
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=0, column=0, columnspan=4, sticky="ew", padx=6, pady=8)
                return

            for row_no, data in enumerate(ordered):
                values = (
                    data["file_type"],
                    data["format_id"],
                    data["archive_format"],
                    self._fmt_count(data["count"]),
                )
                for col, value in enumerate(values):
                    ctk.CTkLabel(
                        table,
                        text=str(value),
                        anchor="e" if col == 3 else "w",
                        justify="right" if col == 3 else "left",
                        font=theme.font(theme.SMALL_SIZE),
                    ).grid(row=row_no, column=col, sticky="ew", padx=6, pady=2)

        def set_sort(key: str):
            if state["key"] == key:
                state["reverse"] = not state["reverse"]
            else:
                state["key"] = key
                state["reverse"] = key == "count"
            render()

        for col, (key, title) in enumerate(columns):
            button = ctk.CTkButton(
                headers,
                text=title,
                command=lambda k=key: set_sort(k),
                anchor="w" if key != "count" else "e",
                height=28,
                fg_color="transparent",
                hover_color=theme.CARD_BORDER,
                text_color=theme.TEXT_MAIN,
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            )
            button.grid(row=0, column=col, sticky="ew", padx=2, pady=(0, 4))
            header_buttons[key] = button

        render()

    def _a2113_show_tooltip(self, event, text: str) -> None:
        """Larger readable archive-title tooltip, still positioned beside pointer."""
        self._a2113_hide_tooltip()
        if not text:
            return

        tooltip = tk.Toplevel(self)
        self._a2113_tooltip = tooltip
        tooltip.wm_overrideredirect(True)
        try:
            tooltip.attributes("-topmost", True)
        except Exception:
            pass

        bg, fg, border = theme.tooltip_colors()
        size = theme.FontRegistry.effective_size(theme.NORMAL_SIZE) + 1
        label = tk.Label(
            tooltip,
            text=text,
            justify="left",
            anchor="w",
            padx=11,
            pady=8,
            relief="solid",
            borderwidth=1,
            wraplength=620,
            background=bg,
            foreground=fg,
            highlightbackground=border,
            font=(theme.FONT_FAMILY, size),
        )
        label.pack()
        self._a2114_place_tooltip()
