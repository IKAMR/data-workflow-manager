from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a23_3 import DepotResultCenterDialogA23_3


class DepotResultCenterDialogA23_4(DepotResultCenterDialogA23_3):
    """a23.4: clearer distribution bars in Resultat og evidens."""

    def _a233_distribution(self, parent, row: int, title: str, rows: list[tuple[str, int]], *, limit: int = 12) -> None:
        card = ctk.CTkFrame(parent, fg_color=theme.CARD_BG, border_width=1, border_color=theme.CARD_BORDER)
        card.grid(row=row, column=0, sticky="ew", padx=2, pady=(0, 8))
        card.grid_columnconfigure(0, weight=0, minsize=185)
        card.grid_columnconfigure(1, weight=0, minsize=110)
        card.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            card, text=title, anchor="w",
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(9, 7))

        shown = list(rows[:limit])
        if not shown:
            ctk.CTkLabel(
                card, text="Ingen materialiserte fordelingsverdier.", anchor="w",
                text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(3, 12))
            return

        total = sum(max(0, int(count or 0)) for _name, count in rows)
        maximum = max((max(0, int(count or 0)) for _name, count in shown), default=1) or 1

        for idx, (name, count) in enumerate(shown, start=1):
            count = max(0, int(count or 0))
            share = (count / total * 100.0) if total else 0.0
            ctk.CTkLabel(
                card, text=str(name), anchor="w", justify="left",
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=idx, column=0, sticky="ew", padx=(10, 10), pady=7)
            ctk.CTkLabel(
                card, text=f"{self._fmt_count(count)}   {share:5.1f} %", anchor="e",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=idx, column=1, sticky="e", padx=(0, 12), pady=7)

            # Make the distribution read as a real bar, not a thin progress line.
            bar_box = ctk.CTkFrame(card, height=24, fg_color=theme.BUTTON_BG, corner_radius=6)
            bar_box.grid(row=idx, column=2, sticky="ew", padx=(0, 12), pady=7)
            bar_box.grid_propagate(False)
            bar_box.grid_columnconfigure(0, weight=1)
            bar_box.grid_rowconfigure(0, weight=1)
            bar = ctk.CTkProgressBar(bar_box, height=18, corner_radius=5)
            bar.grid(row=0, column=0, sticky="ew", padx=3, pady=3)
            bar.set(count / maximum if maximum else 0)

        footer_row = len(shown) + 1
        extra = len(rows) - len(shown)
        footer = f"Sum: {self._fmt_count(total)}"
        if extra > 0:
            footer += f"   ·   + {extra} flere verdier"
        ctk.CTkLabel(
            card, text=footer, anchor="w", text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=footer_row, column=0, columnspan=3, sticky="ew", padx=10, pady=(7, 10))
