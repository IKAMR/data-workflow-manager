from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a23_8 import DepotResultCenterDialogA23_8


class DepotResultCenterDialogA23_9(DepotResultCenterDialogA23_8):
    """a23.9: identical visible distribution bars for one, many and all archive parts.

    The materialized values were already correct for aggregate selections.  The
    previous three-column layout could push percentage/bar columns outside the
    visible evidence card when aggregate values needed more horizontal space.
    Each distribution row now uses a two-line responsive layout: value labels on
    top and a full-width bar below.  The same renderer is used for every scope.
    """

    def _a233_distribution(
        self,
        parent,
        row: int,
        title: str,
        rows: list[tuple[str, int]],
        *,
        limit: int = 12,
    ) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color=theme.CARD_BG,
            border_width=1,
            border_color=theme.CARD_BORDER,
        )
        card.grid(row=row, column=0, sticky="ew", padx=2, pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text=title,
            anchor="w",
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(9, 7))

        shown = list(rows[:limit])
        if not shown:
            ctk.CTkLabel(
                card,
                text="Ingen materialiserte fordelingsverdier.",
                anchor="w",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, sticky="ew", padx=10, pady=(3, 12))
            return

        total = sum(max(0, int(count or 0)) for _name, count in rows)
        maximum = max(
            (max(0, int(count or 0)) for _name, count in shown),
            default=1,
        ) or 1

        grid_row = 1
        for name, count in shown:
            count = max(0, int(count or 0))
            share = (count / total * 100.0) if total else 0.0

            item = ctk.CTkFrame(card, fg_color="transparent")
            item.grid(
                row=grid_row,
                column=0,
                sticky="ew",
                padx=10,
                pady=(4, 5),
            )
            item.grid_columnconfigure(0, weight=1)
            item.grid_columnconfigure(1, weight=0)

            ctk.CTkLabel(
                item,
                text=str(name),
                anchor="w",
                justify="left",
                font=theme.font(theme.SMALL_SIZE),
            ).grid(
                row=0,
                column=0,
                sticky="ew",
                padx=(0, 10),
                pady=(0, 3),
            )

            ctk.CTkLabel(
                item,
                text=f"{self._fmt_count(count)}   {share:5.1f} %",
                anchor="e",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(
                row=0,
                column=1,
                sticky="e",
                pady=(0, 3),
            )

            # Full-width bar below the labels.  It cannot disappear to the
            # right when aggregate counts or long labels widen the text cells.
            bar_box = ctk.CTkFrame(
                item,
                height=24,
                fg_color=theme.BUTTON_BG,
                corner_radius=6,
            )
            bar_box.grid(
                row=1,
                column=0,
                columnspan=2,
                sticky="ew",
            )
            bar_box.grid_propagate(False)
            bar_box.grid_columnconfigure(0, weight=1)
            bar_box.grid_rowconfigure(0, weight=1)

            bar = ctk.CTkProgressBar(
                bar_box,
                height=18,
                corner_radius=5,
            )
            bar.grid(row=0, column=0, sticky="ew", padx=3, pady=3)
            bar.set(count / maximum if maximum else 0.0)

            grid_row += 1

        extra = len(rows) - len(shown)
        footer = f"Sum: {self._fmt_count(total)}"
        if extra > 0:
            footer += f"   ·   + {extra} flere verdier"

        ctk.CTkLabel(
            card,
            text=footer,
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(
            row=grid_row,
            column=0,
            sticky="ew",
            padx=10,
            pady=(5, 10),
        )
