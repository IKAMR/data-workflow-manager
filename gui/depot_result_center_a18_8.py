from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a18_5 import DepotResultCenterDialogA18_5
from .depot_result_views_a29 import _missing_archive_fields


def _overview_metrics(model: dict) -> dict[str, object]:
    """Build presentation-only overview metrics from the materialized report model."""
    summary = model.get("summary") or {}
    real_parts = [
        row for row in (model.get("archive_parts") or [])
        if not row.get("is_all_archive_parts")
    ]
    complete = sum(1 for row in real_parts if not _missing_archive_fields(row))
    missing = max(0, len(real_parts) - complete)
    review_points = model.get("review_points") or model.get("deviations") or []
    if not isinstance(review_points, list):
        review_points = []
    technical = model.get("technical_validation") or {}
    arkade = ((model.get("external_validation") or {}).get("arkade5") or {})
    pronom = arkade.get("pronom_summary") or {}

    return {
        "archive_count": summary.get("archive_count"),
        "archive_part_count": summary.get("archive_part_count") or len(real_parts),
        "complete_archive_parts": complete,
        "missing_archive_parts": missing,
        "review_points": len(review_points),
        "technical_status": technical.get("status") or "–",
        "arkade_runs": len(arkade.get("imports") or []),
        "pronom_rows": pronom.get("statistics_rows", 0),
        "folder_count": summary.get("folder_count"),
        "registration_count": summary.get("registration_count"),
        "journalpost_count": summary.get("journalpost_count"),
        "document_description_count": summary.get("document_description_count"),
        "document_object_count": summary.get("document_object_count"),
    }


class DepotResultCenterDialogA18_8(DepotResultCenterDialogA18_5):
    """a18.8: compact visual overview using only the existing depot report."""

    def _build_overview_tab(self, tab) -> None:
        metrics = _overview_metrics(self.model)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            tab,
            text="Oversikt",
            anchor="w",
            font=theme.font(theme.HEADER_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        counts = ctk.CTkFrame(tab, fg_color="transparent")
        counts.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 7))
        for col in range(4):
            counts.grid_columnconfigure(col, weight=1, uniform="a188counts")

        count_specs = (
            (metrics["archive_part_count"], "Arkivdeler"),
            (metrics["registration_count"], "Registreringer"),
            (metrics["journalpost_count"], "Journalposter"),
            (metrics["document_object_count"], "Dokumentobjekter"),
        )
        for col, (value, label) in enumerate(count_specs):
            self._a188_card(counts, col, self._fmt_count(value), label)

        status = ctk.CTkFrame(tab, fg_color="transparent")
        status.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 7))
        for col in range(4):
            status.grid_columnconfigure(col, weight=1, uniform="a188status")

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
            self._a188_card(status, col, str(value), label)

        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1, uniform="a188body")
        body.grid_columnconfigure(1, weight=1, uniform="a188body")
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            left,
            text="Datagrunnlag",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 5))

        total = int(metrics["archive_part_count"] or 0)
        complete = int(metrics["complete_archive_parts"] or 0)
        ratio = (complete / total) if total else 0.0
        progress = ctk.CTkProgressBar(left)
        progress.grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 7))
        progress.set(max(0.0, min(1.0, ratio)))
        ctk.CTkLabel(
            left,
            text=(
                f"{complete} av {total} arkivdeler har komplett materialisert datagrunnlag.\n"
                f"{metrics['missing_archive_parts']} arkivdeler har manglende felt som må gjennomgås."
            ),
            anchor="nw",
            justify="left",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))
        ctk.CTkButton(
            left,
            text="Gå til Arkivdeler",
            command=lambda: self._a188_show_tab("Arkivdeler"),
        ).grid(row=3, column=0, sticky="w", padx=14, pady=(0, 12))

        right = ctk.CTkFrame(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            right,
            text="Kontrollgrunnlag",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 5))
        ctk.CTkLabel(
            right,
            text=(
                f"Arkade 5-kjøringer: {metrics['arkade_runs']}\n"
                f"PRONOM-statistikkrader: {metrics['pronom_rows']}\n"
                f"Vurderingspunkter: {metrics['review_points']}\n\n"
                "Oversikten leser bare den allerede genererte depotrapporten."
            ),
            anchor="nw",
            justify="left",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 12))
        ctk.CTkButton(
            actions,
            text="Filformater",
            width=110,
            command=lambda: self._a188_show_tab("Filformater"),
        ).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(
            actions,
            text="Depotvurdering",
            width=130,
            command=lambda: self._a188_show_tab("Depotvurdering"),
        ).grid(row=0, column=1)

    def _a188_card(self, parent, column: int, value: str, label: str) -> None:
        card = ctk.CTkFrame(parent)
        card.grid(row=0, column=column, sticky="nsew", padx=4)
        ctk.CTkLabel(
            card,
            text=value,
            anchor="w",
            font=theme.font(theme.TITLE_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(9, 1))
        ctk.CTkLabel(
            card,
            text=label,
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 9))

    def _a188_show_tab(self, name: str) -> None:
        tabs = self._root_tabview()
        if tabs is None:
            return
        try:
            tabs.set(name)
        except Exception:
            pass
