from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a18_8 import _overview_metrics
from .depot_result_center_a18_9 import _control_distribution
from .depot_result_center_a19_1 import (
    DepotResultCenterDialogA19_1,
    _correspondence_profile,
)


class DepotResultCenterDialogA19_2(DepotResultCenterDialogA19_1):
    """a19.2: tighter overview and directly readable correspondence profile."""

    def _build_overview_tab(self, tab) -> None:
        metrics = _overview_metrics(self.model)
        distribution = _control_distribution(self.model)
        correspondence = _correspondence_profile(self.model)

        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(
            tab,
            text="Oversikt",
            anchor="w",
            font=theme.font(theme.HEADER_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 5))

        # Four domain summaries remain cards, but are intentionally shallow so
        # they read as summary fields rather than large clickable panels.
        domains = ctk.CTkFrame(tab, fg_color="transparent")
        domains.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 7))
        for col in range(4):
            domains.grid_columnconfigure(col, weight=1, uniform="a192domains")

        archive_detail = ""
        archive_count = metrics.get("archive_count")
        try:
            if archive_count is not None and int(archive_count) > 1:
                archive_detail = f"{self._fmt_count(archive_count)} arkiv"
        except (TypeError, ValueError):
            archive_detail = ""

        self._a192_domain_field(
            domains, 0, self._fmt_count(metrics.get("archive_part_count")), "Arkivdel", archive_detail
        )
        self._a192_domain_field(
            domains, 1, self._fmt_count(metrics.get("folder_count")), "Mappe / sak"
        )
        self._a192_domain_field(
            domains, 2, self._fmt_count(metrics.get("registration_count")), "Registrering / JP"
        )
        self._a192_domain_field(
            domains, 3, self._fmt_count(metrics.get("document_description_count")), "Dokument"
        )

        # Existing DWM distribution retained, but compacted to avoid competing
        # visually with the domain summary and correspondence profile.
        control = ctk.CTkFrame(tab)
        control.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 7))
        control.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            control,
            text="Resultatfordeling – DWM-kontroller",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(7, 4))

        dist = ctk.CTkFrame(control, fg_color="transparent")
        dist.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 7))
        for col in range(4):
            dist.grid_columnconfigure(col, weight=1, uniform="a192dist")
        total_tests = int(distribution.get("total") or 0)
        for col, (value, label) in enumerate((
            (distribution["ok"], "OK"),
            (distribution["error"], "Feil"),
            (distribution["not_run"], "Ikke kjørt"),
            (distribution["other"], "Annet"),
        )):
            percent = round((value / total_tests) * 100) if total_tests else 0
            self._a192_distribution_field(dist, col, value, label, percent, total_tests)

        self._a192_correspondence_panel(tab, row=3, profile=correspondence)

        # Status row is kept, but made visually denser and grouped as one band.
        status = ctk.CTkFrame(tab)
        status.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 7))
        for col in range(4):
            status.grid_columnconfigure(col, weight=1, uniform="a192status")
        status_specs = (
            (f"{metrics['complete_archive_parts']} / {metrics['archive_part_count']}", "Komplett datagrunnlag"),
            (str(metrics["missing_archive_parts"]), "Arkivdeler med mangler"),
            (str(metrics["review_points"]), "Vurderingspunkter"),
            (str(metrics["technical_status"]), "Teknisk status"),
        )
        for col, (value, label) in enumerate(status_specs):
            self._a192_status_field(status, col, value, label)

        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.grid(row=5, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1, uniform="a192body")
        body.grid_columnconfigure(1, weight=1, uniform="a192body")
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body)
        left.grid(row=0, column=0, sticky="new", padx=(0, 5))
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            left,
            text="Datagrunnlag",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(9, 3))
        total_parts = int(metrics["archive_part_count"] or 0)
        complete = int(metrics["complete_archive_parts"] or 0)
        ratio = (complete / total_parts) if total_parts else 0.0
        progress = ctk.CTkProgressBar(left)
        progress.grid(row=1, column=0, sticky="ew", padx=14, pady=(1, 4))
        progress.set(max(0.0, min(1.0, ratio)))
        ctk.CTkLabel(
            left,
            text=(
                f"{complete} av {total_parts} arkivdeler har komplett materialisert datagrunnlag.  "
                f"{metrics['missing_archive_parts']} har mangler."
            ),
            anchor="w",
            justify="left",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 5))
        ctk.CTkButton(
            left,
            text="Gå til Arkivdeler",
            width=120,
            command=lambda: self._a188_show_tab("Arkivdeler"),
        ).grid(row=3, column=0, sticky="w", padx=14, pady=(0, 9))

        right = ctk.CTkFrame(body)
        right.grid(row=0, column=1, sticky="new", padx=(5, 0))
        right.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            right,
            text="Kontrollgrunnlag",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(9, 3))
        ctk.CTkLabel(
            right,
            text=(
                f"DWM-kontroller: {distribution['total']}  |  "
                f"Arkade 5-kjøringer: {metrics['arkade_runs']}  |  "
                f"PRONOM-statistikkrader: {metrics['pronom_rows']}  |  "
                f"Vurderingspunkter: {metrics['review_points']}"
            ),
            anchor="w",
            justify="left",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 5))
        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 9))
        ctk.CTkButton(
            actions,
            text="Filformater",
            width=105,
            command=lambda: self._a188_show_tab("Filformater"),
        ).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(
            actions,
            text="Depotvurdering",
            width=125,
            command=lambda: self._a188_show_tab("Depotvurdering"),
        ).grid(row=0, column=1)

    def _a192_domain_field(self, parent, column: int, value: str, label: str, detail: str = "") -> None:
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER, corner_radius=5)
        card.grid(row=0, column=column, sticky="nsew", padx=4)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card, text=value, anchor="w",
            font=theme.font(theme.TITLE_SIZE + 1, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=11, pady=(6, 0))
        text = label if not detail else f"{label}  ·  {detail}"
        ctk.CTkLabel(
            card, text=text, anchor="w", text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=1, column=0, sticky="ew", padx=11, pady=(0, 6))

    def _a192_distribution_field(self, parent, column: int, value: int, label: str, percent: int, total: int) -> None:
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER, corner_radius=4)
        card.grid(row=0, column=column, sticky="nsew", padx=4)
        ctk.CTkLabel(
            card, text=f"{percent}%  {label}", anchor="center",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=6, pady=(5, 0))
        ctk.CTkLabel(
            card, text=f"{value} / {total}" if total else "0 / 0", anchor="center",
            text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 5))

    def _a192_correspondence_panel(self, tab, *, row: int, profile: dict[str, int]) -> None:
        panel = ctk.CTkFrame(tab)
        panel.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 7))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel,
            text="Korrespondanseprofil – journalposter",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(7, 4))

        total = sum(profile.values())
        if total <= 0:
            ctk.CTkLabel(
                panel,
                text="Ikke tilgjengelig i materialisert kdrs.c15-kontrollgrunnlag.",
                anchor="w",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 7))
            return

        # Four equal cells remove the ambiguity of a separate stacked bar and
        # legend. Each label, value and local bar now belong to the same cell.
        row_frame = ctk.CTkFrame(panel, fg_color="transparent")
        row_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 7))
        specs = (
            ("incoming", "Inngående", theme.BLUE),
            ("outgoing", "Utgående", theme.CATEGORY_COLORS["Innhold"]),
            ("note", "Notat", theme.CATEGORY_COLORS["Metadata"]),
            ("other", "Andre", theme.TEXT_MUTED),
        )
        for col, (key, label, color) in enumerate(specs):
            row_frame.grid_columnconfigure(col, weight=1, uniform="a192corr")
            value = int(profile.get(key) or 0)
            percent = round((value / total) * 100) if total else 0
            cell = ctk.CTkFrame(row_frame, fg_color="transparent")
            cell.grid(row=0, column=col, sticky="ew", padx=4)
            cell.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                cell,
                text=f"{label}  {percent}%  ·  {self._fmt_count(value)}",
                anchor="w",
                text_color=theme.TEXT_SUB,
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=0, column=0, sticky="ew", pady=(0, 3))
            track = ctk.CTkProgressBar(
                cell,
                height=8,
                progress_color=color,
                fg_color=theme.PANEL_BG_DARK,
            )
            track.grid(row=1, column=0, sticky="ew")
            track.set(max(0.0, min(1.0, value / total)))

    def _a192_status_field(self, parent, column: int, value: str, label: str) -> None:
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=0, column=column, sticky="ew", padx=9, pady=5)
        ctk.CTkLabel(
            cell,
            text=f"{value}  {label}",
            anchor="w",
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
