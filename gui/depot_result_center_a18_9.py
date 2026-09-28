from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a18_8 import DepotResultCenterDialogA18_8, _overview_metrics


def _control_distribution(model: dict) -> dict[str, int]:
    """Return a presentation-only distribution from materialized DWM test rows."""
    tests = ((model.get("technical_validation") or {}).get("tests") or [])
    counts = {"ok": 0, "error": 0, "not_run": 0, "other": 0}
    for row in tests:
        status = row.get("status")
        if status == "ok":
            counts["ok"] += 1
        elif status == "error":
            counts["error"] += 1
        elif status == "disabled_by_legacy_source":
            counts["not_run"] += 1
        else:
            counts["other"] += 1
    counts["total"] = sum(counts.values())
    return counts


class DepotResultCenterDialogA18_9(DepotResultCenterDialogA18_8):
    """a18.9: domain-oriented overview cards and compact control distribution."""

    def _build_overview_tab(self, tab) -> None:
        metrics = _overview_metrics(self.model)
        distribution = _control_distribution(self.model)

        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            tab,
            text="Oversikt",
            anchor="w",
            font=theme.font(theme.HEADER_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        cards = ctk.CTkFrame(tab, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        for col in range(4):
            cards.grid_columnconfigure(col, weight=1, uniform="a189domains")

        archive_detail = ""
        archive_count = metrics.get("archive_count")
        try:
            if archive_count is not None and int(archive_count) > 1:
                archive_detail = f"{self._fmt_count(archive_count)} arkiv"
        except (TypeError, ValueError):
            archive_detail = ""

        self._a189_domain_card(
            cards, 0,
            self._fmt_count(metrics.get("archive_part_count")),
            "Arkivdel",
            archive_detail,
        )
        self._a189_domain_card(
            cards, 1,
            self._fmt_count(metrics.get("folder_count")),
            "Mappe / sak",
        )
        self._a189_domain_card(
            cards, 2,
            self._fmt_count(metrics.get("registration_count")),
            "Registrering / JP",
        )
        self._a189_domain_card(
            cards, 3,
            self._fmt_count(metrics.get("document_description_count")),
            "Dokument",
        )

        control = ctk.CTkFrame(tab)
        control.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        control.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            control,
            text="Resultatfordeling – DWM-kontroller",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(11, 6))

        dist = ctk.CTkFrame(control, fg_color="transparent")
        dist.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        for col in range(4):
            dist.grid_columnconfigure(col, weight=1, uniform="a189dist")

        dist_specs = (
            (distribution["ok"], "OK"),
            (distribution["error"], "Feil"),
            (distribution["not_run"], "Ikke kjørt"),
            (distribution["other"], "Annet"),
        )
        total = int(distribution["total"] or 0)
        for col, (value, label) in enumerate(dist_specs):
            percent = round((value / total) * 100) if total else 0
            self._a189_distribution_card(dist, col, value, label, percent, total)

        status = ctk.CTkFrame(tab, fg_color="transparent")
        status.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
        for col in range(4):
            status.grid_columnconfigure(col, weight=1, uniform="a189status")

        status_specs = (
            (
                f"{metrics['complete_archive_parts']} / {metrics['archive_part_count']}",
                "Komplett datagrunnlag",
            ),
            (metrics["missing_archive_parts"], "Arkivdeler med mangler"),
            (metrics["review_points"], "Vurderingspunkter"),
            (metrics["technical_status"], "Teknisk status"),
        )
        for col, (value, label) in enumerate(status_specs):
            self._a189_status_card(status, col, str(value), label)

        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.grid(row=4, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1, uniform="a189body")
        body.grid_columnconfigure(1, weight=1, uniform="a189body")
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body)
        left.grid(row=0, column=0, sticky="new", padx=(0, 5))
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            left,
            text="Datagrunnlag",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))

        total_parts = int(metrics["archive_part_count"] or 0)
        complete = int(metrics["complete_archive_parts"] or 0)
        ratio = (complete / total_parts) if total_parts else 0.0
        progress = ctk.CTkProgressBar(left)
        progress.grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 5))
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
        ).grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 7))
        ctk.CTkButton(
            left,
            text="Gå til Arkivdeler",
            width=120,
            command=lambda: self._a188_show_tab("Arkivdeler"),
        ).grid(row=3, column=0, sticky="w", padx=14, pady=(0, 10))

        right = ctk.CTkFrame(body)
        right.grid(row=0, column=1, sticky="new", padx=(5, 0))
        right.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            right,
            text="Kontrollgrunnlag",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
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
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 7))

        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))
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

    def _a189_domain_card(
        self,
        parent,
        column: int,
        value: str,
        label: str,
        detail: str = "",
    ) -> None:
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER)
        card.grid(row=0, column=column, sticky="nsew", padx=4)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card,
            text=value,
            anchor="w",
            font=theme.font(theme.TITLE_SIZE + 2, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=13, pady=(10, 0))
        ctk.CTkLabel(
            card,
            text=label,
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=1, column=0, sticky="ew", padx=13, pady=(1, 0))
        ctk.CTkLabel(
            card,
            text=detail or " ",
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=2, column=0, sticky="ew", padx=13, pady=(0, 9))

    def _a189_distribution_card(
        self,
        parent,
        column: int,
        value: int,
        label: str,
        percent: int,
        total: int,
    ) -> None:
        card = ctk.CTkFrame(parent, border_width=1, border_color=theme.CARD_BORDER)
        card.grid(row=0, column=column, sticky="nsew", padx=4)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card,
            text=f"{percent}%",
            anchor="center",
            font=theme.font(theme.TITLE_SIZE + 1, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        ctk.CTkLabel(
            card,
            text=label,
            anchor="center",
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=1, column=0, sticky="ew", padx=8)
        ctk.CTkLabel(
            card,
            text=f"{value} / {total}" if total else "0 / 0",
            anchor="center",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 7))

    def _a189_status_card(self, parent, column: int, value: str, label: str) -> None:
        card = ctk.CTkFrame(parent)
        card.grid(row=0, column=column, sticky="nsew", padx=4)
        ctk.CTkLabel(
            card,
            text=value,
            anchor="w",
            font=theme.font(theme.TITLE_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(7, 0))
        ctk.CTkLabel(
            card,
            text=label,
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 7))
