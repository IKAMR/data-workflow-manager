from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from . import theme
from .depot_result_center_a21_5 import DepotResultCenterDialogA21_5


class DepotResultCenterDialogA21_6(DepotResultCenterDialogA21_5):
    """a21.6: clearer extraction period spacing and a compact period indicator.

    The period indicator uses only already materialized declared, observed and
    reviewed years.  It does not calculate a new Noark analysis result.
    Arkivdeler remains unchanged in this step.
    """

    def _a211_period_card(self, parent, column: int, period: dict[str, object]) -> None:
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER, corner_radius=7)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 5))

        # Label | breathing room | start | dash | end | flexible remainder.
        card.grid_columnconfigure(0, weight=0, minsize=82)
        card.grid_columnconfigure(1, weight=0, minsize=16)
        card.grid_columnconfigure(2, weight=0, minsize=48)
        card.grid_columnconfigure(3, weight=0, minsize=18)
        card.grid_columnconfigure(4, weight=0, minsize=48)
        card.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(
            card,
            text="Tidsprofil – hele uttrekket",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, columnspan=6, sticky="ew", padx=12, pady=(9, 4))

        rows = (
            ("Oppgitt", period.get("declared_start"), period.get("declared_end")),
            ("Observert", period.get("observed_start"), period.get("observed_end")),
            ("Vurdert", period.get("reviewed_start"), period.get("reviewed_end")),
        )
        for row_no, (label, start, end) in enumerate(rows, start=1):
            ctk.CTkLabel(
                card,
                text=label,
                anchor="w",
                text_color=theme.TEXT_SUB,
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=row_no, column=0, sticky="w", padx=(12, 0), pady=0)
            ctk.CTkLabel(
                card,
                text=str(start if start is not None else "–"),
                anchor="e",
                text_color=theme.TEXT_SUB,
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=row_no, column=2, sticky="e", pady=0)
            ctk.CTkLabel(
                card,
                text="–",
                anchor="center",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=row_no, column=3, sticky="ew", pady=0)
            ctk.CTkLabel(
                card,
                text=str(end if end is not None else "–"),
                anchor="w",
                text_color=theme.TEXT_SUB,
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=row_no, column=4, sticky="w", pady=0)

        canvas = tk.Canvas(
            card,
            height=48,
            background=theme.PANEL_BG,
            highlightthickness=0,
            bd=0,
        )
        canvas.grid(row=4, column=0, columnspan=6, sticky="ew", padx=12, pady=(11, 3))
        payload = dict(period)
        canvas.bind(
            "<Configure>",
            lambda _event, c=canvas, p=payload: self._a216_draw_period_indicator(c, p),
            add="+",
        )

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
        ).grid(row=5, column=0, columnspan=6, sticky="ew", padx=12, pady=(4, 8))

    @staticmethod
    def _a216_int_year(value):
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _a216_draw_period_indicator(self, canvas: tk.Canvas, period: dict[str, object]) -> None:
        try:
            canvas.delete("all")
            width = max(180, int(canvas.winfo_width()))
        except Exception:
            return

        observed_start = self._a216_int_year(period.get("observed_start"))
        observed_end = self._a216_int_year(period.get("observed_end"))
        reviewed_start = self._a216_int_year(period.get("reviewed_start"))
        reviewed_end = self._a216_int_year(period.get("reviewed_end"))
        declared_start = self._a216_int_year(period.get("declared_start"))
        declared_end = self._a216_int_year(period.get("declared_end"))
        outliers = sorted({
            y for y in (self._a216_int_year(v) for v in (period.get("outliers") or [])) if y is not None
        })

        # Main scale follows observed/reviewed activity. A far technical year
        # such as 2099 is shown separately instead of compressing the timeline.
        starts = [v for v in (observed_start, reviewed_start, declared_start) if v is not None]
        normal_ends = [v for v in (observed_end, reviewed_end) if v is not None]
        if not starts or not normal_ends:
            return
        main_start = min(starts)
        main_end = max(normal_ends)
        if declared_end is not None and declared_end <= main_end + 5:
            main_end = max(main_end, declared_end)
        if main_end <= main_start:
            main_end = main_start + 1

        detached = [y for y in outliers if y < main_start - 2 or y > main_end + 2]
        right_zone = 76 if detached else 8
        x0 = 8
        x1 = max(x0 + 60, width - right_zone)
        y = 20
        canvas.create_line(x0, y, x1, y, fill=theme.CARD_BORDER, width=2)

        def xpos(year):
            if year is None:
                return None
            ratio = (year - main_start) / max(1, main_end - main_start)
            ratio = max(0.0, min(1.0, ratio))
            return x0 + ratio * (x1 - x0)

        # Observed span: muted factual range.
        ox0, ox1 = xpos(observed_start), xpos(observed_end)
        if ox0 is not None and ox1 is not None:
            canvas.create_line(ox0, y, ox1, y, fill=theme.TEXT_SUB, width=5)

        # Reviewed span: stronger blue overlay, matching the reviewed-year
        # markers already established in Arkivdeler.
        rx0, rx1 = xpos(reviewed_start), xpos(reviewed_end)
        if rx0 is not None and rx1 is not None:
            canvas.create_line(rx0, y, rx1, y, fill=theme.BLUE, width=3)
            canvas.create_line(rx0, 8, rx0, 32, fill=theme.BLUE, width=2)
            canvas.create_line(rx1, 8, rx1, 32, fill=theme.BLUE, width=2)

        canvas.create_text(x0, 40, text=str(main_start), anchor="sw", fill=theme.TEXT_MUTED)
        canvas.create_text(x1, 40, text=str(main_end), anchor="se", fill=theme.TEXT_MUTED)

        if detached:
            canvas.create_text(x1 + 9, y, text="//", anchor="w", fill=theme.TEXT_MUTED)
            shown = str(detached[-1]) if len(detached) == 1 else f"{detached[0]}…{detached[-1]}"
            canvas.create_text(width - 4, y, text=shown, anchor="e", fill=theme.TEXT_MUTED)
