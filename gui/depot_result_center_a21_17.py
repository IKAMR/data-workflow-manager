from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from . import theme
from .depot_result_center_a21_15 import DepotResultCenterDialogA21_15


class DepotResultCenterDialogA21_17(DepotResultCenterDialogA21_15):
    """a21.17: search beside title and wider rich format hover."""

    @staticmethod
    def _a2116_first(raw: dict, *keys: str) -> str:
        for key in keys:
            value = raw.get(key)
            if value not in (None, ""):
                return " ".join(str(value).split())
        return ""

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
                puid = str(raw.get("format_id") or "–")
                full_name = self._a2116_first(raw, "format_name", "name", "file_type", "format") or puid
                version = self._a2116_first(raw, "format_version", "version", "formatVersion")
                mime = self._a2116_first(
                    raw,
                    "mime_type", "mime", "mimetype", "mimeType", "media_type", "mediaType",
                )
                rows.append({
                    "format_id": puid,
                    "file_type": self._a2114_display_format_name(raw),
                    "full_name": full_name,
                    "format_version": version,
                    "mime_type": mime,
                    "archive_format": str(raw.get("raf_220301") or "–"),
                    "count": count,
                })
        return rows

    @staticmethod
    def _a2116_tooltip_text(row: dict) -> str:
        lines = [row.get("file_type") or "Ukjent format"]
        full_name = str(row.get("full_name") or "").strip()
        if full_name and full_name != row.get("file_type"):
            lines.append(f"Fullt navn: {full_name}")
        puid = str(row.get("format_id") or "").strip()
        if puid:
            lines.append(f"PUID: {puid}")
        version = str(row.get("format_version") or "").strip()
        if version and version not in {"-", "–", "—"}:
            lines.append(f"Versjon: {version}")
        mime = str(row.get("mime_type") or "").strip()
        if mime and mime not in {"-", "–", "—"}:
            lines.append(f"MIME: {mime}")
        status = str(row.get("archive_format") or "").strip()
        if status:
            lines.append(f"Arkivformatstatus: {status}")
        lines.append(f"Antall: {int(row.get('count') or 0):,}".replace(",", " "))
        return "\n".join(lines)

    def _a2117_show_format_tooltip(self, event, text: str) -> None:
        """Wide tooltip for format metadata, kept close to the pointer."""
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

        label = tk.Label(
            tooltip,
            text=text,
            justify="left",
            anchor="w",
            padx=12,
            pady=8,
            relief="solid",
            borderwidth=1,
            wraplength=1100,
            font=(theme.FONT_FAMILY, theme.FontRegistry.effective_size(theme.TOOLTIP_SIZE + 1)),
        )
        label.pack()
        tooltip.update_idletasks()

        try:
            pointer_x = int(event.x_root)
            pointer_y = int(event.y_root)
        except Exception:
            pointer_x = 0
            pointer_y = 0
        x = pointer_x + 16
        y = pointer_y + 16
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            width = tooltip.winfo_reqwidth()
            height = tooltip.winfo_reqheight()
            if x + width > screen_w - 8:
                x = max(8, pointer_x - width - 16)
            if y + height > screen_h - 8:
                y = max(8, pointer_y - height - 16)
        except Exception:
            pass
        tooltip.wm_geometry(f"+{x}+{y}")

    def _replace_pronom_text_with_table(self, tab) -> None:
        old = getattr(self, "_a14_pronom_text", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass

        # A compact search field belongs beside the Filformater / PRONOM title.
        search_var = ctk.StringVar(value="")
        search = ctk.CTkEntry(
            tab,
            textvariable=search_var,
            width=330,
            height=30,
            placeholder_text="Søk i filformater, PUID, MIME ...",
            font=theme.font(theme.SMALL_SIZE),
        )
        search.place(x=215, y=14, anchor="nw")
        self._a2116_format_search = search

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

        # Exactly the same column geometry is used for headers and data.
        widths = (360, 150, 190, 120)
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
        header_labels = {}

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
                    header_labels[key].configure(text=title + marker)
                except Exception:
                    pass

        def filtered_rows():
            needle = search_var.get().strip().casefold()
            if not needle:
                return rows
            result = []
            for row in rows:
                hay = " ".join(str(row.get(k) or "") for k in (
                    "file_type", "full_name", "format_id", "format_version",
                    "mime_type", "archive_format", "count",
                )).casefold()
                if needle in hay:
                    result.append(row)
            return result

        def render(*_args):
            clear_table()
            ordered = sorted(
                filtered_rows(),
                key=lambda row: self._a2114_sort_value(row, state["key"]),
                reverse=state["reverse"],
            )
            refresh_headers()
            if not ordered:
                ctk.CTkLabel(
                    table,
                    text="Ingen filformater matcher søket.",
                    anchor="w",
                    text_color=theme.TEXT_MUTED,
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=0, column=0, columnspan=4, sticky="ew", padx=6, pady=8)
                return

            for row_no, data in enumerate(ordered):
                values = (
                    data["file_type"], data["format_id"], data["archive_format"], self._fmt_count(data["count"]),
                )
                for col, value in enumerate(values):
                    label = ctk.CTkLabel(
                        table,
                        text=str(value),
                        anchor="e" if col == 3 else "w",
                        justify="right" if col == 3 else "left",
                        font=theme.font(theme.SMALL_SIZE),
                    )
                    label.grid(row=row_no, column=col, sticky="ew", padx=(6, 6), pady=2)
                    if col == 0:
                        tip = self._a2116_tooltip_text(data)
                        label.bind("<Enter>", lambda event, t=tip: self._a2117_show_format_tooltip(event, t), add="+")
                        label.bind("<Motion>", lambda event: self._a2114_place_tooltip(), add="+")
                        label.bind("<Leave>", lambda event: self._a2113_hide_tooltip(), add="+")

        def set_sort(key: str):
            if state["key"] == key:
                state["reverse"] = not state["reverse"]
            else:
                state["key"] = key
                state["reverse"] = key == "count"
            render()

        for col, (key, title) in enumerate(columns):
            label = ctk.CTkLabel(
                headers,
                text=title,
                anchor="e" if key == "count" else "w",
                text_color=theme.TEXT_MAIN,
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
                cursor="hand2",
            )
            label.grid(row=0, column=col, sticky="ew", padx=(6, 6), pady=(0, 4))
            label.bind("<Button-1>", lambda event, k=key: set_sort(k), add="+")
            header_labels[key] = label

        search_var.trace_add("write", render)
        render()
