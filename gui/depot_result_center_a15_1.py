from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from . import theme
from .depot_result_center_a14_4 import DepotResultCenterDialogA14_4
from .depot_result_views_a29 import _missing_archive_fields
from .depot_result_views_a22 import _identity


class DepotResultCenterDialogA15_1(DepotResultCenterDialogA14_4):
    """a15.1: compact annual-volume view for each archive part."""

    _SERIES = (
        ("folder", "Mappe/sak"),
        ("journal", "Registrering/JP"),
        ("document_description", "Dok.beskrivelse"),
        ("document_object", "Dok.objekt"),
    )

    def __init__(self, master, **kwargs) -> None:
        # These attributes must exist before the inherited constructor runs:
        # older layers call the virtual _show_archive_part() while building the UI.
        self._a15_year_canvas = None
        self._a15_year_status = None
        self._a15_year_panel = None
        self._a15_year_index = 0
        super().__init__(master, **kwargs)
        self._install_a15_yearly_volume_panel()
        self._refresh_a15_archive_cards()
        if getattr(self, "_archive_parts", None):
            self._render_a15_yearly_volume(self._archive_index)

    @staticmethod
    def _year(value) -> int | None:
        text = str(value or "").strip()
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
        return None

    @staticmethod
    def _series(row: dict, key: str) -> dict[int, int]:
        raw = (row.get("yearly_volume") or {}).get(key) or {}
        out: dict[int, int] = {}
        if not isinstance(raw, dict):
            return out
        for year, count in raw.items():
            try:
                y = int(str(year)[:4])
                n = int(count)
            except (TypeError, ValueError):
                continue
            if 1000 <= y <= 2999 and n >= 0:
                out[y] = out.get(y, 0) + n
        return dict(sorted(out.items()))

    def _periods(self, row: dict) -> tuple[tuple[int | None, int | None], tuple[int | None, int | None]]:
        identity = row.get("archive_part") or {}
        reported = (
            self._year(identity.get("archive_period_start_date")),
            self._year(identity.get("archive_period_end_date")),
        )
        observed_years: list[int] = []
        for key, _label in self._SERIES:
            observed_years.extend(
                year for year, count in self._series(row, key).items() if count > 0
            )
        observed = (
            min(observed_years) if observed_years else None,
            max(observed_years) if observed_years else None,
        )
        return reported, observed

    @staticmethod
    def _period_text(period: tuple[int | None, int | None]) -> str:
        first, last = period
        if first is None and last is None:
            return "–"
        if first is None:
            return f"–{last}"
        if last is None:
            return f"{first}–"
        return f"{first}–{last}"

    def _install_a15_yearly_volume_panel(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None or not getattr(self, "_archive_parts", None):
            return
        try:
            tab = tabs.tab("Sammendrag")
        except Exception:
            return

        # a11 moved the existing scrollable content to row 3. Keep it expandable
        # below the compact annual-volume panel.
        for child in tab.winfo_children():
            try:
                info = child.grid_info()
            except Exception:
                continue
            if str(info.get("row")) == "3":
                child.grid_configure(row=4)

        tab.grid_rowconfigure(3, weight=0)
        tab.grid_rowconfigure(4, weight=1)

        panel = ctk.CTkFrame(tab)
        panel.grid(row=3, column=0, sticky="ew", padx=4, pady=(0, 8))
        panel.grid_columnconfigure(0, weight=1)
        self._a15_year_panel = panel

        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            head,
            text="Omfang per år",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        self._a15_year_status = ctk.CTkLabel(
            head,
            text="",
            anchor="e",
            justify="right",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a15_year_status.grid(row=0, column=1, sticky="e", padx=(12, 0))

        canvas = tk.Canvas(
            panel,
            height=154,
            bg=theme.PANEL_BG,
            highlightthickness=0,
            bd=0,
        )
        canvas.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 9))
        canvas.bind("<Configure>", lambda _event: self._redraw_a15_year_chart(), add="+")
        self._a15_year_canvas = canvas

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if self._a15_year_canvas is not None:
            self._render_a15_yearly_volume(index)

    def _render_a15_yearly_volume(self, index: int) -> None:
        if self._a15_year_canvas is None:
            return
        self._a15_year_index = index
        row = self._archive_parts[index]
        reported, observed = self._periods(row)

        notes = [
            f"Oppgitt: {self._period_text(reported)}",
            f"Observert: {self._period_text(observed)}",
        ]
        if all(v is not None for v in reported + observed):
            r0, r1 = reported
            o0, o1 = observed
            if o0 < r0 or o1 > r1:
                notes.append("aktivitet utenfor oppgitt periode")
            elif (o0, o1) != (r0, r1):
                notes.append("ytterår avviker")
        if self._a15_year_status is not None:
            self._a15_year_status.configure(text="  ·  ".join(notes))
        self._redraw_a15_year_chart()

    def _redraw_a15_year_chart(self) -> None:
        canvas = self._a15_year_canvas
        if canvas is None or not getattr(self, "_archive_parts", None):
            return
        index = getattr(self, "_a15_year_index", getattr(self, "_archive_index", 0))
        if not (0 <= index < len(self._archive_parts)):
            return
        row = self._archive_parts[index]
        series = [(key, label, self._series(row, key)) for key, label in self._SERIES]
        reported, observed = self._periods(row)

        years = set()
        for _key, _label, values in series:
            years.update(values)
        years.update(y for y in reported if y is not None)
        if not years:
            canvas.delete("all")
            canvas.create_text(
                12, 70,
                text="Årsfordeling er ikke materialisert ennå. Kjør Noark 5-testene og bygg resultatvisning/rapport på nytt.",
                anchor="w",
                fill=theme.TEXT_MUTED,
                font=(theme.FONT_FAMILY, theme.SMALL_SIZE),
            )
            return

        first, last = min(years), max(years)
        if reported[0] is not None:
            first = min(first, reported[0])
        if reported[1] is not None:
            last = max(last, reported[1])
        if last <= first:
            last = first + 1

        canvas.delete("all")
        width = max(640, canvas.winfo_width())
        left, right, top = 132, 88, 8
        plot_w = max(100, width - left - right)
        strip_h = 30

        def x_for(year: int) -> float:
            return left + ((year - first) / (last - first)) * plot_w

        # Reported archive period is a reference, not an automatically trusted fact.
        for yr in reported:
            if yr is None:
                continue
            x = x_for(yr)
            canvas.create_line(
                x, top, x, top + strip_h * len(series),
                fill=theme.TEXT_MUTED,
                dash=(3, 3),
            )

        year_span = last - first + 1
        bar_w = max(1.0, min(8.0, plot_w / max(year_span, 1) * 0.72))
        for idx, (_key, label, values) in enumerate(series):
            y0 = top + idx * strip_h
            baseline = y0 + 22
            canvas.create_text(
                4, baseline - 8,
                text=label,
                anchor="w",
                fill=theme.TEXT,
                font=(theme.FONT_FAMILY, theme.SMALL_SIZE),
            )
            canvas.create_line(left, baseline, left + plot_w, baseline, fill=theme.CARD_BORDER)
            maximum = max(values.values(), default=0)
            total = sum(values.values())
            if maximum > 0:
                for year, count in values.items():
                    if count <= 0:
                        continue
                    x = x_for(year)
                    h = max(1.0, 18.0 * (count / maximum))
                    canvas.create_rectangle(
                        x - bar_w / 2,
                        baseline - h,
                        x + bar_w / 2,
                        baseline,
                        fill=theme.BLUE,
                        outline="",
                    )
            canvas.create_text(
                left + plot_w + 8,
                baseline - 8,
                text=f"Σ {total:,}".replace(",", " "),
                anchor="w",
                fill=theme.TEXT_SUB,
                font=(theme.FONT_FAMILY, theme.SMALL_SIZE),
            )

        bottom = top + strip_h * len(series)
        canvas.create_text(
            left, bottom + 8,
            text=str(first),
            anchor="nw",
            fill=theme.TEXT_MUTED,
            font=(theme.FONT_FAMILY, theme.SMALL_SIZE),
        )
        canvas.create_text(
            left + plot_w, bottom + 8,
            text=str(last),
            anchor="ne",
            fill=theme.TEXT_MUTED,
            font=(theme.FONT_FAMILY, theme.SMALL_SIZE),
        )

    def _refresh_a15_archive_cards(self) -> None:
        for index, button in enumerate(getattr(self, "_archive_buttons", [])):
            row = self._archive_parts[index]
            system_id, title = _identity(row, index)
            missing = _missing_archive_fields(row)
            data_line = (
                f"Datagrunnlag: mangler {len(missing)}"
                if missing
                else "Datagrunnlag: komplett"
            )
            reported, observed = self._periods(row)
            period = (
                f"Periode {self._period_text(reported)} · obs. {self._period_text(observed)}"
                if reported != (None, None) or observed != (None, None)
                else "Periode –"
            )
            button.configure(
                text=(
                    f"{system_id}\n"
                    f"{title}\n"
                    f"{data_line}  |  {period}  |  Behandling: {self.REVIEW_NOT_STARTED}"
                ),
                height=88,
            )
