from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from . import theme
from .depot_result_center_a19_4 import DepotResultCenterDialogA19_4, _period_profile_layout


class DepotResultCenterDialogA19_5(DepotResultCenterDialogA19_4):
    """a19.5: readable three-series period profiles and a richer archive-part fact profile."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        if getattr(self, "_archive_parts", None):
            self._a195_render_fact_profile(getattr(self, "_archive_index", 0))

    # ------------------------------------------------------------------
    # Period profile: retain one independent chart for each content series.
    # ------------------------------------------------------------------
    def _a194_replace_period_sparklines(self) -> None:
        old_labels = getattr(self, "_a191_period_spark_labels", None) or []
        if len(old_labels) != 3:
            return
        self._a194_period_canvases = []
        self._a194_period_payloads = [{}, {}, {}]
        for index, label in enumerate(old_labels):
            try:
                parent = label.master
                info = dict(label.grid_info())
                label.grid_remove()
            except Exception:
                continue
            canvas = tk.Canvas(
                parent,
                height=52,
                background=theme.PANEL_BG,
                highlightthickness=0,
                bd=0,
            )
            # Keep the exact column occupied by the old sparkline.  a19.4 put
            # all canvases in column 0, causing them to cover each other.
            canvas.grid(
                row=int(info.get("row", 0)),
                column=int(info.get("column", index)),
                columnspan=int(info.get("columnspan", 1)),
                sticky="ew",
                padx=info.get("padx", (0 if index == 0 else 8, 8)),
                pady=(0, 0),
            )
            canvas.bind("<Configure>", lambda _event, i=index: self._a194_draw_period_profile(i), add="+")
            self._a194_period_canvases.append(canvas)

    def _a194_draw_period_profile(self, index: int) -> None:
        if not (0 <= index < len(self._a194_period_canvases)):
            return
        if not (0 <= index < len(self._a194_period_payloads)):
            return
        canvas = self._a194_period_canvases[index]
        payload = self._a194_period_payloads[index] or {}
        try:
            canvas.delete("all")
            width = max(150, int(canvas.winfo_width()))
            height = max(48, int(canvas.winfo_height()))
        except Exception:
            return

        main_start = payload.get("main_start")
        main_end = payload.get("main_end")
        if main_start is None or main_end is None:
            canvas.create_text(4, height // 2, text="–", anchor="w", fill=theme.TEXT_MUTED)
            return

        values = payload.get("values") or {}
        left_outliers = list(payload.get("left_outliers") or [])
        right_outliers = list(payload.get("right_outliers") or [])
        assessed_start = payload.get("assessed_start")
        assessed_end = payload.get("assessed_end")

        left_zone = 34 if left_outliers else 0
        right_zone = 58 if right_outliers else 0
        gap = 10 if (left_outliers or right_outliers) else 0
        x0 = 4 + left_zone + (gap if left_outliers else 0)
        x1 = width - 4 - right_zone - (gap if right_outliers else 0)
        if x1 <= x0 + 24:
            x0, x1 = 4, width - 4

        marker_top = 1
        chart_top = 7
        baseline = height - 15
        main_years = list(range(int(main_start), int(main_end) + 1))
        all_years = main_years + left_outliers + right_outliers
        peak = max((int(values.get(y, 0) or 0) for y in all_years), default=0)
        peak = max(1, peak)

        canvas.create_line(x0, baseline, x1, baseline, fill=theme.CARD_BORDER, width=1)
        slot = max(1.0, (x1 - x0) / max(1, len(main_years)))
        bar_width = max(1.0, min(10.0, slot * 0.72))
        for pos, year in enumerate(main_years):
            value = int(values.get(year, 0) or 0)
            if value <= 0:
                continue
            cx = x0 + (pos + 0.5) * slot
            bar_h = max(2.0, (value / peak) * (baseline - chart_top))
            canvas.create_rectangle(
                cx - bar_width / 2, baseline - bar_h,
                cx + bar_width / 2, baseline,
                fill=theme.TEXT_SUB, outline="",
            )

        def marker_x(year):
            if year is None or year < main_start or year > main_end:
                return None
            return x0 + (int(year) - int(main_start) + 0.5) * slot

        # Assessment boundaries deliberately extend above and below the bars so
        # they remain obvious at +2 font scaling and on dense year profiles.
        for year in (assessed_start, assessed_end):
            mx = marker_x(year)
            if mx is not None:
                canvas.create_line(mx, marker_top, mx, baseline + 6, fill=theme.BLUE, width=2)

        if left_outliers:
            canvas.create_text(2, baseline - 13, text="…", anchor="w", fill=theme.TEXT_MUTED)
            year = max(left_outliers, key=lambda y: int(values.get(y, 0) or 0))
            value = int(values.get(year, 0) or 0)
            bar_h = max(2.0, (value / peak) * (baseline - chart_top))
            canvas.create_rectangle(18, baseline - bar_h, 24, baseline, fill=theme.TEXT_MUTED, outline="")
            canvas.create_text(2, baseline + 2, text=str(year), anchor="nw", fill=theme.TEXT_MUTED)
        if right_outliers:
            canvas.create_text(x1 + 3, baseline - 13, text="…", anchor="w", fill=theme.TEXT_MUTED)
            year = max(right_outliers, key=lambda y: int(values.get(y, 0) or 0))
            value = int(values.get(year, 0) or 0)
            bar_h = max(2.0, (value / peak) * (baseline - chart_top))
            ox = min(width - 18, x1 + 24)
            canvas.create_rectangle(ox, baseline - bar_h, ox + 6, baseline, fill=theme.TEXT_MUTED, outline="")
            canvas.create_text(x1 + 3, baseline + 2, text=str(year), anchor="nw", fill=theme.TEXT_MUTED)

        canvas.create_text(x0, baseline + 2, text=str(main_start), anchor="nw", fill=theme.TEXT_MUTED)
        canvas.create_text(x1, baseline + 2, text=str(main_end), anchor="ne", fill=theme.TEXT_MUTED)

    # ------------------------------------------------------------------
    # Complete, low-priority fact profile below the fast assessment surface.
    # ------------------------------------------------------------------
    @staticmethod
    def _a195_value(value) -> str:
        if value is None or value == "":
            return "–"
        if isinstance(value, dict):
            items = []
            for key, count in value.items():
                try:
                    shown = f"{int(count):,}".replace(",", " ")
                except (TypeError, ValueError):
                    shown = str(count)
                items.append((str(key), shown))
            return " · ".join(f"{key}: {shown}" for key, shown in items) or "–"
        if isinstance(value, list):
            return " · ".join(str(item) for item in value) or "–"
        try:
            if isinstance(value, int):
                return f"{value:,}".replace(",", " ")
        except Exception:
            pass
        return str(value)

    def _a195_fact_rows(self, index: int) -> list[tuple[str, list[tuple[str, object]]]]:
        row = self._archive_parts[index]
        folder = self._values_for_row("folders", row)
        registration = self._values_for_row("registrations", row)
        journal = self._values_for_row("journalposts", row)
        description = self._values_for_row("descriptions", row)
        obj = self._values_for_row("objects", row)

        groups: list[tuple[str, list[tuple[str, object]]]] = [
            ("Mappe / sak", [
                ("Mapper", folder.get("folder_count", row.get("folder_count"))),
                ("Saker (saksmappe)", self._case_count_for_row(row)),
                ("Mappetyper", folder.get("type_counts") or folder.get("folder_type_counts")),
                ("Mappestatus", folder.get("status_counts") or folder.get("folder_status_counts")),
            ]),
            ("Registrering / journalpost", [
                ("Registreringer", registration.get("registration_count", row.get("registration_count"))),
                ("Journalposter", journal.get("journalpost_count", row.get("journalpost_count"))),
                ("Registreringstyper", registration.get("type_counts")),
                ("Journalposttyper", journal.get("journalpost_type_counts")),
                ("Journalstatus", journal.get("journal_status_counts")),
            ]),
            ("Dokument", [
                ("Dokumentbeskrivelser", description.get("document_description_count", row.get("document_description_count"))),
                ("Dokumentobjekter", obj.get("document_object_count", row.get("document_object_count"))),
                ("Tilknytning til registrering", description.get("relation_type_counts")),
                ("Dokumenttype", description.get("document_type_counts")),
                ("Dokumentstatus", description.get("document_status_counts")),
                ("Dokumentmedium", description.get("document_medium_counts")),
                ("Variantformat", obj.get("variant_format_counts")),
                ("Versjonsnummer", obj.get("version_number_counts")),
                ("Format (metadata)", obj.get("format_counts")),
            ]),
            ("Bevaring, skjerming og kassasjon", [
                ("Skjerminger", row.get("screening_count")),
                ("Kassasjonsvedtak", row.get("disposal_decision_count")),
                ("Utført kassasjon", row.get("performed_disposal_count")),
                ("Slettinger", row.get("deletion_count")),
            ]),
        ]

        # The detailed materialized presentation may contain additional per-part
        # metadata (for example correspondence parties). Append those fields
        # rather than maintaining a second hard-coded whitelist.
        known_labels = {label.casefold() for _title, rows in groups for label, _value in rows}
        extras: list[tuple[str, object]] = []
        for section in self._sections_for_index(index):
            for field in section.get("fields") or []:
                if str(field.get("status") or "") != "ok":
                    continue
                label = str(field.get("label") or field.get("id") or "Felt")
                value = field.get("value")
                if label.casefold() in known_labels or value in (None, "", {}, []):
                    continue
                known_labels.add(label.casefold())
                extras.append((label, value))
        if extras:
            groups.append(("Andre materialiserte metadata", extras))
        return groups

    def _a195_render_fact_profile(self, index: int) -> None:
        frame = getattr(self, "_assessment_surface", None)
        if frame is None or not getattr(self, "_archive_parts", None):
            return
        # Remove only our own previous a19.5 block; inherited assessment remains.
        old = getattr(self, "_a195_fact_panel", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass

        panel = ctk.CTkFrame(frame)
        next_row = max(
            [int(child.grid_info().get("row", 0)) for child in frame.winfo_children() if child.grid_info()] + [0]
        ) + 1
        panel.grid(row=next_row, column=0, sticky="ew", padx=4, pady=(2, 12))
        panel.grid_columnconfigure(1, weight=1)
        self._a195_fact_panel = panel

        ctk.CTkLabel(
            panel, text="Detaljert faktaprofil", anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            panel,
            text="Materialiserte metadata for valgt arkivdel. Ingen ny analyse kjøres i denne visningen.",
            anchor="w", text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))

        cursor = 2
        for title, rows in self._a195_fact_rows(index):
            visible = [(label, value) for label, value in rows if value not in (None, "", {}, [])]
            if not visible:
                continue
            ctk.CTkLabel(
                panel, text=title, anchor="w",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=cursor, column=0, columnspan=2, sticky="ew", padx=12, pady=(7, 2))
            cursor += 1
            for label, value in visible:
                ctk.CTkLabel(
                    panel, text=label, anchor="nw", text_color=theme.TEXT_SUB,
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=cursor, column=0, sticky="nw", padx=(18, 8), pady=1)
                ctk.CTkLabel(
                    panel, text=self._a195_value(value), anchor="nw", justify="left",
                    wraplength=920, font=theme.font(theme.SMALL_SIZE),
                ).grid(row=cursor, column=1, sticky="ew", padx=(8, 12), pady=1)
                cursor += 1

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if hasattr(self, "_assessment_surface"):
            self._a195_render_fact_profile(index)
