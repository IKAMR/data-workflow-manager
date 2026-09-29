from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a21_3 import DepotResultCenterDialogA21_3


class DepotResultCenterDialogA21_4(DepotResultCenterDialogA21_3):
    """a21.4: readable overview format list and full-width PRONOM table.

    This step deliberately leaves Arkivdeler unchanged.  It only addresses the
    two presentation issues confirmed after a21.3: count-first overview rows and
    the PRONOM scrollbar/Antall clipping problem.
    """

    def _a211_formats_card(
        self,
        parent,
        column: int,
        formats: list[tuple[str, str, int]],
        metrics: dict[str, object],
    ) -> None:
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
            lines = []
            for name, puid, count in formats:
                identity = f"{name} ({puid})" if puid else name
                lines.append(f"{self._fmt_count(count):>9}  ·  {identity}")
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

    def _replace_pronom_text_with_table(self, tab) -> None:
        """Build a PRONOM table that really occupies the whole Filformater tab.

        Older result-view layers left a narrow table frame in column 0.  Its
        internal scrollbar therefore appeared around the middle of the window
        and covered the Antall column.  a21.4 owns the complete tab width and
        reserves explicit space for Antall before the scrollbar.
        """
        old = getattr(self, "_a14_pronom_text", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass

        # Neutralise grid columns inherited from earlier Filformater layouts.
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

        # CTkScrollableFrame's scrollbar now sits at the right edge because the
        # frame itself fills the tab.  The final data column also gets generous
        # right padding so the scrollbar can never cover the values.
        table = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        table.grid(row=1, column=0, sticky="nsew")
        table.grid_columnconfigure(0, weight=0, minsize=125)
        table.grid_columnconfigure(1, weight=1, minsize=300)
        table.grid_columnconfigure(2, weight=0, minsize=150)
        table.grid_columnconfigure(3, weight=0, minsize=150)
        table.grid_columnconfigure(4, weight=0, minsize=125)

        headers = ("Format-ID / PUID", "Filtype", "Formatversjon", "RAF-220301", "Antall")
        for col, heading in enumerate(headers):
            ctk.CTkLabel(
                table,
                text=heading,
                anchor="e" if col == 4 else "w",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(
                row=0,
                column=col,
                sticky="ew",
                padx=(6, 26 if col == 4 else 6),
                pady=(4, 7),
            )

        row_no = 1
        for item in imports:
            pronom = item.get("pronom") or {}
            if not pronom.get("available"):
                continue
            stats = pronom.get("statistics") or {}
            for data in list(stats.get("rows") or []):
                values = (
                    data.get("format_id") or "–",
                    data.get("file_type") or "–",
                    data.get("format_version") or "–",
                    data.get("raf_220301") or "–",
                    data.get("count") if data.get("count") is not None else "–",
                )
                for col, value in enumerate(values):
                    ctk.CTkLabel(
                        table,
                        text=str(value),
                        anchor="e" if col == 4 else "w",
                        justify="right" if col == 4 else "left",
                        font=theme.font(theme.SMALL_SIZE),
                    ).grid(
                        row=row_no,
                        column=col,
                        sticky="ew",
                        padx=(6, 26 if col == 4 else 6),
                        pady=2,
                    )
                row_no += 1

        if row_no == 1:
            ctk.CTkLabel(
                table,
                text="Ingen PRONOM-statistikk er materialisert i depotrapporten.",
                anchor="w",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, columnspan=5, sticky="ew", padx=6, pady=8)
