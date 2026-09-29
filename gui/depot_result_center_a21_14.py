from __future__ import annotations

import re

import customtkinter as ctk

from . import theme
from .depot_result_center_a21_13 import DepotResultCenterDialogA21_13


class DepotResultCenterDialogA21_14(DepotResultCenterDialogA21_13):
    """a21.14: readable format names, sortable PRONOM table and local hover tooltip."""

    _PUID_FRIENDLY = {
        "fmt/354": "PDF/A-1b",
        "fmt/95": "PDF/A-1a",
        "fmt/477": "PDF/A-2b",
        "fmt/480": "PDF/A-3b",
        "fmt/476": "PDF/A-2a",
        "fmt/479": "PDF/A-3a",
        "fmt/412": "Microsoft Word (DOCX)",
        "fmt/40": "Microsoft Word (DOC)",
        "fmt/214": "Microsoft Excel (XLSX)",
        "fmt/61": "Microsoft Excel (XLS)",
    }

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

        # Prefer an explicit, human-readable PDF/A identity over the very long
        # PRONOM label. The separate PUID is still shown beside it.
        if "PDF/A" in raw.upper() and re.fullmatch(r"[123][abu]?", version, flags=re.I):
            return f"PDF/A-{version}"
        if puid in cls._PUID_FRIENDLY:
            return cls._PUID_FRIENDLY[puid]

        upper = raw.upper()
        if "PORTABLE DOCUMENT FORMAT" in upper and version and version not in {"-", "–"}:
            return f"PDF {version}"

        return cls._a215_short_format_name(raw or puid or "Ukjent format", max_chars=52)

    def _a211_top_formats(self) -> list[tuple[str, str, int]]:
        arkade = ((self.model.get("external_validation") or {}).get("arkade5") or {})
        totals: dict[tuple[str, str], int] = {}
        for item in arkade.get("imports") or []:
            stats = ((item.get("pronom") or {}).get("statistics") or {})
            for row in stats.get("rows") or []:
                puid = str(row.get("format_id") or "").strip()
                name = self._a2114_display_format_name(row)
                try:
                    count = int(row.get("count") or 0)
                except (TypeError, ValueError):
                    count = 0
                key = (name, puid)
                totals[key] = totals.get(key, 0) + count
        return [
            (name, puid, count)
            for (name, puid), count in sorted(
                totals.items(), key=lambda item: (-item[1], item[0][0].lower(), item[0][1])
            )[:5]
        ]

    def _a211_formats_card(self, parent, column: int, formats, metrics) -> None:
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER, corner_radius=7)
        card.grid(row=0, column=column, sticky="nsew", padx=5)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card,
            text="Filformater",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 4))

        if formats:
            lines = [
                f"{self._fmt_count(count):>9}  ·  {name} ({puid})" if puid
                else f"{self._fmt_count(count):>9}  ·  {name}"
                for name, puid, count in formats
            ]
            text = "\n".join(lines)
        else:
            text = (
                f"{self._fmt_count(metrics.get('pronom_rows')):>9}  ·  PRONOM-statistikkrader\n"
                "Ingen toppformater materialisert."
            )

        ctk.CTkLabel(
            card,
            text=text,
            anchor="nw",
            justify="left",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

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
                    "format_version": str(raw.get("format_version") or "–"),
                    "raf_220301": str(raw.get("raf_220301") or "–"),
                    "count": count,
                })
        return rows

    @staticmethod
    def _a2114_sort_value(row: dict, key: str):
        value = row.get(key)
        if key == "count":
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return 0
        return str(value or "").casefold()

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
        panel.grid_rowconfigure(2, weight=1)

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
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        headers = ctk.CTkFrame(panel, fg_color="transparent")
        headers.grid(row=1, column=0, sticky="ew")
        table = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        table.grid(row=2, column=0, sticky="nsew")

        widths = (125, 370, 145, 120, 95)
        for holder in (headers, table):
            for col, width in enumerate(widths):
                holder.grid_columnconfigure(col, weight=0, minsize=width)
            holder.grid_columnconfigure(5, weight=1, minsize=12)

        columns = (
            ("format_id", "Format-ID / PUID"),
            ("file_type", "Filtype"),
            ("format_version", "Formatversjon"),
            ("raf_220301", "RAF-220301"),
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
                ).grid(row=0, column=0, columnspan=5, sticky="ew", padx=6, pady=8)
                return

            for row_no, data in enumerate(ordered):
                values = (
                    data["format_id"],
                    data["file_type"],
                    data["format_version"],
                    data["raf_220301"],
                    self._fmt_count(data["count"]),
                )
                for col, value in enumerate(values):
                    ctk.CTkLabel(
                        table,
                        text=str(value),
                        anchor="e" if col == 4 else "w",
                        justify="right" if col == 4 else "left",
                        font=theme.font(theme.SMALL_SIZE),
                    ).grid(row=row_no, column=col, sticky="w", padx=6, pady=2)

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
                anchor="w",
                height=28,
                fg_color="transparent",
                hover_color=theme.CARD_BORDER,
                text_color=theme.TEXT_MAIN,
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            )
            button.grid(row=0, column=col, sticky="w", padx=2, pady=(0, 4))
            header_buttons[key] = button

        render()

    def _a2114_place_tooltip(self, _event=None) -> None:
        tooltip = getattr(self, "_a2113_tooltip", None)
        if tooltip is None:
            return
        try:
            x = int(self.winfo_pointerx()) + 16
            y = int(self.winfo_pointery()) + 12
            tooltip.wm_geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _a2113_show_tooltip(self, event, text: str) -> None:
        # Let a21.13 create the exact same tooltip, then place it beside the
        # *current mouse pointer* rather than relying on the widget Enter event.
        super()._a2113_show_tooltip(event, text)
        self._a2114_place_tooltip()

    def _a2113_bind_full_title(self, button, raw_title: str, shown_title: str) -> None:
        super()._a2113_bind_full_title(button, raw_title, shown_title)
        if raw_title.strip() != shown_title.strip():
            button.bind("<Motion>", self._a2114_place_tooltip, add="+")
        else:
            button.unbind("<Motion>")
