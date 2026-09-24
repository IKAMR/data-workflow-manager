
from __future__ import annotations

import customtkinter as ctk

from noark5_workflow.external_evidence.arkade5_gap_analysis import (
    build_gap_overlap_analysis,
)
from . import theme
from .depot_result_views_a20 import DepotResultViewsDialogA20


_RELATION_LABELS = {
    "equivalent": "Ekvivalent",
    "partial": "Delvis overlapp",
    "complementary": "Komplementær",
    "arkade_only": "Kun Arkade",
    "unmapped": "Ikke kartlagt",
}


class ArkadeGapOverlapDialogA27(ctk.CTkToplevel):
    """v0.1.5-a27: readable static DWM/Arkade gap and overlap view."""

    def __init__(self, master) -> None:
        super().__init__(master)
        self.title("DWM / Arkade 5 – gap og overlapp")
        self.geometry("1120x760")
        self.minsize(820, 560)
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text="DWM / Arkade 5 – gap og overlapp",
            anchor="w",
            font=theme.font(theme.HEADER_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))

        self.loading = ctk.CTkLabel(
            self,
            text="Laster gap- og overlappoversikt …",
            anchor="center",
            justify="center",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.NORMAL_SIZE),
        )
        self.loading.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)

        self.update_idletasks()
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

        # Paint the window/loading state before building the static model.
        self.after(75, self._build_content)

    @staticmethod
    def _dwm_text(area: dict) -> str:
        parts = []
        for item in area.get("dwm") or []:
            test_id = str(item.get("dwm_test_id") or "–")
            name = str(item.get("name") or "").strip()
            parts.append(f"{test_id} – {name}" if name else test_id)
        return "; ".join(parts) or "–"

    def _build_content(self) -> None:
        try:
            model = build_gap_overlap_analysis()
        except Exception as exc:
            self.loading.configure(
                text=f"Kunne ikke bygge gap- og overlappoversikten:\n{exc}"
            )
            return

        summary = model.get("summary") or {}
        self.loading.destroy()

        body = ctk.CTkScrollableFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            body,
            text=(
                "Statisk kunnskapsmodell – ikke dokumentasjon på at en kontroll er kjørt. "
                "Arkade-, DWM- og historiske KDRS-identifikatorer holdes adskilt."
            ),
            anchor="w",
            justify="left",
            wraplength=1040,
            text_color=theme.TEXT_MUTED,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(
            body,
            text=(
                f"Arkade-kontroller: {summary.get('arkade_test_count', 0)}   |   "
                f"Kun Arkade: {summary.get('dwm_gaps_covered_by_arkade', 0)}   |   "
                f"Overlapp: {summary.get('overlap_control_areas', 0)}   |   "
                f"Kun DWM: {summary.get('dwm_only', 0)}"
            ),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(0, 12))

        only_arkade = ctk.CTkFrame(body)
        only_arkade.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        only_arkade.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            only_arkade,
            text="Kontroller kun i Arkade 5",
            anchor="w",
            font=theme.font(theme.BODY_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

        arkade_only_rows = [
            item
            for item in model.get("arkade_control_areas") or []
            if item.get("relation") == "arkade_only"
        ]
        for idx, area in enumerate(arkade_only_rows, start=1):
            ctk.CTkLabel(
                only_arkade,
                text=(
                    f"{area.get('arkade_test_id') or '–'} – "
                    f"{area.get('arkade_test_name') or 'Uten testnavn'}"
                ),
                anchor="w",
                justify="left",
                wraplength=1020,
            ).grid(row=idx, column=0, sticky="ew", padx=14, pady=1)

        overlap = ctk.CTkFrame(body)
        overlap.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        overlap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            overlap,
            text="Overlapp mellom DWM og Arkade 5",
            anchor="w",
            font=theme.font(theme.BODY_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

        overlap_rows = [
            item
            for item in model.get("arkade_control_areas") or []
            if item.get("relation") != "arkade_only"
        ]
        for idx, area in enumerate(overlap_rows, start=1):
            relation = _RELATION_LABELS.get(
                area.get("relation"),
                area.get("relation") or "–",
            )
            ctk.CTkLabel(
                overlap,
                text=(
                    f"{area.get('arkade_test_id') or '–'} – "
                    f"{area.get('arkade_test_name') or 'Uten testnavn'}"
                    f"  |  {relation}"
                    f"  |  DWM: {self._dwm_text(area)}"
                ),
                anchor="w",
                justify="left",
                wraplength=1020,
            ).grid(row=idx, column=0, sticky="ew", padx=14, pady=1)

        dwm_only = ctk.CTkFrame(body)
        dwm_only.grid(row=4, column=0, sticky="ew")
        dwm_only.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dwm_only,
            text="Kontroller kun i DWM",
            anchor="w",
            font=theme.font(theme.BODY_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

        dwm_only_rows = model.get("dwm_only") or []
        if not dwm_only_rows:
            ctk.CTkLabel(
                dwm_only,
                text="Ingen dokumenterte kontroller kun i DWM.",
                anchor="w",
                text_color=theme.TEXT_MUTED,
            ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        else:
            for idx, item in enumerate(dwm_only_rows, start=1):
                test_id = str(item.get("dwm_test_id") or "–")
                name = str(item.get("name") or "").strip()
                ctk.CTkLabel(
                    dwm_only,
                    text=f"{test_id} – {name}" if name else test_id,
                    anchor="w",
                    justify="left",
                    wraplength=1020,
                ).grid(row=idx, column=0, sticky="ew", padx=14, pady=1)

        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass


class DepotResultViewsDialogA21(DepotResultViewsDialogA20):
    """v0.1.5-a27: readable gap/overlap presentation."""

    def _open_gap_overlap(self) -> None:
        ArkadeGapOverlapDialogA27(self)
