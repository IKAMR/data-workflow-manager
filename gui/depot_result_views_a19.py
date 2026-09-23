from __future__ import annotations

import customtkinter as ctk

from noark5_workflow.external_evidence.arkade5_gap_analysis import build_gap_overlap_analysis
from . import theme
from .depot_result_views_a18 import DepotResultViewsDialogA18


_RELATION_LABELS = {
    "equivalent": "Ekvivalent",
    "partial": "Delvis overlapp",
    "complementary": "Komplementær",
    "arkade_only": "DWM-gap / Arkade",
}


class ArkadeGapOverlapDialogA19(ctk.CTkToplevel):
    """Static DWM/Arkade implementation gap and overlap view."""

    def __init__(self, master) -> None:
        super().__init__(master)
        self.title("DWM / Arkade 5 – gap og overlapp")
        self.geometry("980x700")
        self.minsize(760, 520)
        self.transient(master)

        model = build_gap_overlap_analysis()
        summary = model["summary"]

        body = ctk.CTkScrollableFrame(self)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            body,
            text="DWM / Arkade 5 – implementasjonsgap og overlapp",
            anchor="w",
            font=theme.font(theme.HEADER_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(
            body,
            text=(
                "Statisk kunnskapsmodell – ikke dokumentasjon på at en kontroll er kjørt. "
                "Arkade-, DWM- og historiske KDRS-identifikatorer holdes adskilt."
            ),
            anchor="w", justify="left", wraplength=900,
            text_color=theme.TEXT_MUTED,
        ).grid(row=1, column=0, sticky="ew", pady=(0, 10))

        summary_text = (
            f"Arkade-kontroller: {summary['arkade_test_count']}   |   "
            f"DWM-gap dekket av Arkade: {summary['dwm_gaps_covered_by_arkade']}   |   "
            f"Overlapp: {summary['overlap_control_areas']}   |   "
            f"DWM-only: {summary['dwm_only']}"
        )
        ctk.CTkLabel(body, text=summary_text, anchor="w").grid(
            row=2, column=0, sticky="ew", pady=(0, 12)
        )

        gap_frame = ctk.CTkFrame(body)
        gap_frame.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        gap_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            gap_frame, text="Dokumenterte DWM-gap som Arkade 5 dekker",
            anchor="w", font=theme.font(theme.BODY_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        for idx, area in enumerate(
            [a for a in model["arkade_control_areas"] if a["relation"] == "arkade_only"], 1
        ):
            ctk.CTkLabel(
                gap_frame,
                text=f"{area['arkade_test_id']}  {area.get('arkade_test_name') or ''}",
                anchor="w", justify="left",
            ).grid(row=idx, column=0, sticky="ew", padx=14, pady=1)

        overlap_frame = ctk.CTkFrame(body)
        overlap_frame.grid(row=4, column=0, sticky="ew")
        overlap_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            overlap_frame, text="Overlapp mellom DWM og Arkade 5",
            anchor="w", font=theme.font(theme.BODY_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        for idx, area in enumerate(
            [a for a in model["arkade_control_areas"] if a["relation"] != "arkade_only"], 1
        ):
            dwm_ids = ", ".join(x["dwm_test_id"] for x in area["dwm"]) or "–"
            label = _RELATION_LABELS.get(area["relation"], area["relation"])
            ctk.CTkLabel(
                overlap_frame,
                text=f"{area['arkade_test_id']}  {label}  |  DWM: {dwm_ids}",
                anchor="w", justify="left",
            ).grid(row=idx, column=0, sticky="ew", padx=14, pady=1)


class DepotResultViewsDialogA19(DepotResultViewsDialogA18):
    """v0.1.5-a10: expose static DWM/Arkade gap and overlap knowledge."""

    def _build_external_evidence_tab(self, tab) -> None:
        super()._build_external_evidence_tab(tab)
        frame = ctk.CTkFrame(tab, fg_color="transparent")
        frame.grid(row=9, column=0, sticky="ew", padx=8, pady=(0, 8))
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            frame,
            text=(
                "Vis dokumenterte implementasjonsgap og overlapp mellom DWM og Arkade 5. "
                "Dette er statisk mapping, ikke kjørt testdekning."
            ),
            anchor="w", justify="left", wraplength=720,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            frame, text="Gap og overlapp...", width=180,
            command=self._open_gap_overlap,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)

    def _open_gap_overlap(self) -> None:
        dialog = ArkadeGapOverlapDialogA19(self)
        dialog.update_idletasks()
        dialog.lift()
        dialog.focus_force()
